import re
import time
from enum import Enum


DISCORD_MENTION_PATTERN = re.compile(r'<@[0-9]+>', re.DOTALL)
SKIP_LATCH_PATTERN = re.compile(r'\\[^\\].*', re.DOTALL)
CLEAR_LATCH_PATTERN = re.compile(r'\\\\.*', re.DOTALL)


class AutoproxyMode(Enum):
    Off = 0,
    Always = 1,
    Latch_Unlatched = 2
    Latch_Latched = 3


class AutoproxyManager:
    def __init__(self, client, peer_pattern):
        if not isinstance(peer_pattern, re.Pattern):
            self.peer_pattern = re.compile(peer_pattern, re.DOTALL)
        else:
            self.peer_pattern = peer_pattern

        self.client = client
        self.proxy_mode = AutoproxyMode.Off
        self.last_message_time = None

    def handle_command(self, option):
        if option == "off":
            self.proxy_mode = AutoproxyMode.Off

        elif option == "latch":
            self.proxy_mode = AutoproxyMode.Latch_Unlatched

        elif option == self.client.user.mention:
            self.proxy_mode = AutoproxyMode.Always

        elif DISCORD_MENTION_PATTERN.match(option):
            self.proxy_mode = AutoproxyMode.Off

    def on_manual_proxy(self):
        if self.proxy_mode == AutoproxyMode.Latch_Unlatched:
            self.proxy_mode = AutoproxyMode.Latch_Latched
            self.last_message_time = time.time()

    def should_autoproxy(self, message):
        match self.proxy_mode:
            case AutoproxyMode.Off | AutoproxyMode.Latch_Unlatched:
                return False

            case AutoproxyMode.Always:
                return True

            case AutoproxyMode.Latch_Latched:

                if self.peer_pattern.match(message.content) or CLEAR_LATCH_PATTERN.match(message.content):
                    self.proxy_mode = AutoproxyMode.Latch_Unlatched
                    return False

                if SKIP_LATCH_PATTERN.match(message.content):
                    return False

                return True
