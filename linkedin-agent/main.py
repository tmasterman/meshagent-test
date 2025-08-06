import os
import asyncio
from meshagent.api import RequiredToolkit, RoomClient, ParticipantToken
from meshagent.api.services import ServiceHost
from meshagent.agents.chat import ChatBot
from meshagent.agents.mail import MailWorker, SmtpConfiguration, room_address
from meshagent.openai import OpenAIResponsesAdapter
from meshagent.openai.tools.responses_adapter import WebSearchTool
from meshagent.tools import ToolContext, TextResponse
from meshagent.tools import Tool, ToolContext, Toolkit, RemoteToolkit
from meshagent.otel import otel_config
import logging

from meshagent.agents.mail import room_address

logging.basicConfig(level=logging.INFO)

otel_config(service_name="linkedin-service")
log = logging.getLogger("linkedin")

from linkedin_helper import LinkedInClient # need to import after we set up the logging

service = ServiceHost(
    port=int(os.getenv("MESHAGENT_PORT","7778"))
)


def get_linkedin_client() -> LinkedInClient:
    # singleton — created once, reused for the lifetime of the service
    if not hasattr(get_linkedin_client, "_li"):
        get_linkedin_client._li = LinkedInClient()
    return get_linkedin_client._li


class VerifyUserAuth(Tool):
    """Simple probe to make sure the token in env is valid."""
    def __init__(self):
        super().__init__(
            name="verify-linkedin-auth",
            title="verify linkedin auth",
            description="verifies LinkedIn access token & returns profile info",
            input_schema={
                "type": "object", 
                "additionalProperties": False,
                "required":[],
                "properties": {}
                }
        )

    async def execute(self, context: ToolContext):
        try:
            li = get_linkedin_client()
            log.info("linkedin.auth.ok",extra={"linkedin.version": li.version, "linkedin.author_urn": li.author_urn})
            return TextResponse(text=f"LinkedIn auth OK – {li.first_name} {li.last_name}")
        except Exception as exc:
            log.error("linkedin.auth.fail", exc_info=True, extra={"error.message": str(exc)})
            # Bubble a short error that flows back to the chat agent
            #raise RuntimeError(f"LinkedIn auth FAILED: {exc}") from exc
            return TextResponse(text=f"LinkedIn auth FAILED: {exc}")



class PostTexttoLinkedIn(Tool):
    def __init__(self):
        super().__init__(
            name="post-text-to-linkedin",
            title="post text to linkedin",
            description="a tool that publishes a text based post to linkedin",
            input_schema={
                "type": "object",
                "additionalProperties" : False,
                "required":[
                    "post_text"
                ],
                "properties": {
                    "post_text": {"type": "string"}
                    }
                },
        )

    async def execute(self, context: ToolContext, *, post_text: str, visibility: str = "PUBLIC"):
        li = get_linkedin_client()

        # Safety: make sure we never double-post identical text in one process
        if hasattr(self, "_last_post") and self._last_post == post_text:
            return TextResponse(text="Duplicate post suppressed.", success=False)

        try:
            urn = li.post(post_text, visibility=visibility)
            self._last_post = post_text
            return TextResponse(text=f"Posted! URN: {urn}\nVisibility: {visibility}")
        except Exception as exc:
            return TextResponse(text=f"LinkedIn post failed: {exc}", success=False)
        
@service.path("/linkedintools")
class LinkedInToolkit(RemoteToolkit):
    def __init__(self):
        super().__init__(
            name="linkedin-toolkit",
            title="linkedin-toolkit",
            description="a toolkit for posting content to linkedin",
            tools=[VerifyUserAuth(), PostTexttoLinkedIn()]
        )

@service.path("/linkedinagent")
class LinkedInAgent(ChatBot):
    def __init__(self):
        super().__init__(
            name="linkedin-agent",
            title="LinkedIn Agent",
            description="An agent who drafts and posts content to LinkedIn",
            llm_adapter = OpenAIResponsesAdapter(),
            rules=[
                """
                You help users draft and post content to LinkedIn. You work iteratively with the user to draft the right content for their post until they approve it. Once the user approves the post you post it to their LinkedIn. Always verify with the user that they are ready to post the content before you share it to their LinkedIn. 

                You have access to a variety of tools to help you create, refine, and share the content to LinkedIn.  
                """
            ],
            requires=[
                RequiredToolkit(name="ui"), 
                RequiredToolkit(name="linkedin-toolkit")
            ], 
            toolkits=[
                Toolkit(name="web-search", tools=[WebSearchTool()])
                ]
        )

@service.path("/linkedinmailagent")
class LinkedInMailAgent(MailWorker):
    def __init__(self):
        super().__init__(
            name="linkedin-mail-agent", 
            title="linkedin mail agent",
            description="An agent that works with you to draft and post to LinkedIn via email",
            llm_adapter=OpenAIResponsesAdapter(),
            rules=[
                """
                You help users draft and post content to LinkedIn via email. The user will reach out to you for help creating a post and you must use your tools to appropriately research the topic and come up with a draft for the user. You work iteratively with the user to draft the right content for their post until they approve it. 

                Once the user approves the post you post it to their LinkedIn. Always verify with the user that they are ready to post the content before you share it to their LinkedIn.
                """
            ],
            requires=[
                RequiredToolkit(name="linkedin-toolkit")
                ],
            toolkits=[
                Toolkit(name="web-search", tools=[WebSearchTool()]) 
                ],
            domain="mail.meshagent.com",
            # domain="mail.meshagent.life",
            smtp=SmtpConfiguration(
                username="linkedinemail",
                password=os.getenv("MESHAGENT_TOKEN"),
                hostname="mail.meshagent.com"
                )
        )
    async def start(self, *, room: RoomClient):
            parsed_token = ParticipantToken.from_jwt(
                room.protocol.token, validate=False
            )
            print(
                f"Send an email interact with your mailbot: {room_address(project_id=parsed_token.project_id, room_name=room.room_name)}"
            )
            return await super().start(room=room)

print(f"running on port {service.port}")
log.info(f"running on port {service.port}")
log.info("Starting service...")
asyncio.run(service.run())
