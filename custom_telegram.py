from rasa.core.channels import TelegramInput

class TelegramInputChannel(TelegramInput):
    def get_metadata(self, request):
        metadata=request.json
        return metadata