# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

import json
import gspread
from typing import Any, Text, Dict, List
from oauth2client.service_account import ServiceAccountCredentials

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import EventType

INTENT_DESCRIPTION_MAPPING_PATH = "actions/intent_description_mapping.csv"
SH_NAME = 'BraveBot'
GS_CREDENTIAL_MAPPING_PATH = 'gs_credentials.json'

class ActionDefaultAskAffirmation(Action):

    def name(self) -> Text:
        return "action_default_ask_affirmation"

    def __init__(self) -> None:
        import pandas as pd

        self.intent_mappings = pd.read_csv(INTENT_DESCRIPTION_MAPPING_PATH)
        self.intent_mappings.fillna("", inplace=True)
        self.intent_mappings.entities = self.intent_mappings.entities.map(
            lambda entities: {e.strip() for e in entities.split(",")}
        )

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[EventType]:
        intent_ranking = tracker.latest_message.get("intent_ranking", [])
        if len(intent_ranking) > 1:
            diff_intent_confidence = intent_ranking[0].get(
                "confidence"
            ) - intent_ranking[1].get("confidence")
            if diff_intent_confidence < 0.2:
                intent_ranking = intent_ranking[:2]
            else:
                intent_ranking = intent_ranking[:1]

        # for the intent name used to retrieve the button title, we either use
        # the name of the name of the "main" intent, or if it's an intent that triggers
        # the response selector, we use the full retrieval intent name so that we
        # can distinguish between the different sub intents
        first_intent_names = [
            intent.get("name", "")
            if intent.get("name", "") not in ["faq", "chitchat"]
            else tracker.latest_message.get("response_selector")
            .get(intent.get("name", ""))
            .get("full_retrieval_intent")
            for intent in intent_ranking
        ]

        if first_intent_names == ['nlu_fallback', None]:
            dispatcher.utter_message(response='utter_default')
            return []

        message_title = (
            "🤔 Ви мали на увазі... "
        )

        entities = tracker.latest_message.get("entities", [])
        entities = {e["entity"]: e["value"] for e in entities}

        entities_json = json.dumps(entities)

        buttons = []
        for intent in first_intent_names:
            button_title = self.get_button_title(intent, entities)
            if "/" in intent:
                # here we use the button title as the payload as well, because you
                # can't force a response selector sub intent, so we need NLU to parse
                # that correctly
                buttons.append({"title": button_title, "payload": button_title})
            else:
                buttons.append(
                    {"title": button_title, "payload": f"/{intent}{entities_json}"}
                )

        buttons.append({"title": "Інше", "payload": "/trigger_rephrase"})

        dispatcher.utter_message(text=message_title, buttons=buttons)

        return []

    def get_button_title(self, intent: Text, entities: Dict[Text, Text]) -> Text:
        default_utterance_query = self.intent_mappings.intent == intent
        utterance_query = (self.intent_mappings.entities == entities.keys()) & (
            default_utterance_query
        )

        utterances = self.intent_mappings[utterance_query].button.tolist()

        if len(utterances) > 0:
            button_title = utterances[0]
        else:
            utterances = self.intent_mappings[default_utterance_query].button.tolist()
            button_title = utterances[0] if len(utterances) > 0 else intent

        return button_title.format(**entities)

    class ActionGetSenderId(Action):

        def name(self):
            return "action_get_sender_id"

        def __init__(self):
            scope = ['https://spreadsheets.google.com/feeds',
                     'https://www.googleapis.com/auth/spreadsheets',
                     'https://www.googleapis.com/auth/drive.file',
                     'https://www.googleapis.com/auth/drive']

            # Reading Credentails from ServiceAccount Keys file
            credentials = ServiceAccountCredentials.from_json_keyfile_name(GS_CREDENTIAL_MAPPING_PATH, scope)

            # intitialize the authorization object
            self.gc = gspread.authorize(credentials)

        def run(self, dispatcher, tracker, domain):
            input_data = tracker.latest_message
            user_info = input_data["metadata"]["message"]["from"]
            user_id = user_info.get("id")
            user_first_name = user_info.get("first_name")
            user_last_name = user_info.get("last_name")
            user_tg_name = user_info.get("username")
            user_mess = input_data['text']
            intent = self.get_intent_name(tracker)
            main_info = [user_id, user_first_name, user_last_name, user_tg_name, intent, user_mess]
            print(main_info)
            self.save_to_gs(main_info)

        @staticmethod
        def get_intent_name(tracker):
            intent = tracker.latest_message["intent"]['name']

            if intent not in ["faq", "chitchat"]:
                first_intent_names = intent
            else:
                first_intent_names = tracker.latest_message["response_selector"][intent]['ranking'][0]['intent_response_key']

            return first_intent_names

        def save_to_gs(self, info):
            sheet = self.gc.open(SH_NAME)
            try:
                sheet_info = sheet.get_worksheet(0)
                sheet_info.append_row(info)
            except:
                print('Error Occurred')
            return
