import re
import time
from enum import Enum


DISCORD_MENTION_PATTERN = re.compile(r'<@[0-9]+>', re.DOTALL)
SKIP_LATCH_PATTERN = re.compile(r'\\[^\\].*', re.DOTALL)
CLEAR_LATCH_PATTERN = re.compile(r'\\\\.*', re.DOTALL)
DEFAULT_LATCH_MODE = "server"

class AutoproxyMode(Enum):
    Off = 0,
    On = 1,
    Latch_Unlatched = 2
    Latch_Latched = 3

class AutoproxyState:
    def __init__(self):
        self.proxy_mode = AutoproxyMode.Off
        self.last_message_time = time.time()


class AutoproxyManager:
    def __init__(self, client, peer_pattern, latch_scope):
        if not isinstance(peer_pattern, re.Pattern):
            self.peer_pattern = re.compile(peer_pattern, re.DOTALL)
        else:
            self.peer_pattern = peer_pattern

        self.client = client
        self.states = {}
        self.latch_scope = latch_scope or DEFAULT_LATCH_MODE

    def _get_autoproxy_state_key(self, message):
        if self.latch_scope == "global":
            return ''

        if self.latch_scope == 'server':
            return message.guild.id

        if self.latch_scope == 'channel':
            return message.channel.id

    def _get_autoproxy_state(self, message):
        key = self._get_autoproxy_state_key(message)

        if not key in self.states:
            self.states[key] = AutoproxyState()

        return self.states[key]


    def handle_command(self, option, message):
        state = self._get_autoproxy_state(message)

        if option == "off":
            state.proxy_mode = AutoproxyMode.Off

        elif option == "latch":
            state.proxy_mode = AutoproxyMode.Latch_Unlatched

        elif option == self.client.user.mention:
            state.proxy_mode = AutoproxyMode.On
            state.last_message_time = time.time()

        elif DISCORD_MENTION_PATTERN.match(option):
            state.proxy_mode = AutoproxyMode.Off

    def on_manual_proxy(self, message):
        state = self._get_autoproxy_state(message)

        if state.proxy_mode == AutoproxyMode.Latch_Unlatched:
            state.proxy_mode = AutoproxyMode.Latch_Latched
            state.last_message_time = time.time()

    def should_autoproxy(self, message):
        state = self._get_autoproxy_state(message)

        # Single \ at start always skips with no further logic
        if SKIP_LATCH_PATTERN.match(message.content):
            return False

        match state.proxy_mode:
            # Not in autoproxy, or in unlatched state, skip proxy
            case AutoproxyMode.Off | AutoproxyMode.Latch_Unlatched:
                return False

            # When enabled, only autoproxy messages that don't look like a peer's explicit proxy
            case AutoproxyMode.On:
                if self.peer_pattern.match(message.content):
                    return False
                else:
                    state.last_message_time = time.time()
                    return True

            # When latched, clear if we see a peer's message, otherwise proxy it
            case AutoproxyMode.Latch_Latched:
                if self.peer_pattern.match(message.content) or CLEAR_LATCH_PATTERN.match(message.content):
                    state.proxy_mode = AutoproxyMode.Latch_Unlatched
                    return False

                # TODO: check time

                return True
