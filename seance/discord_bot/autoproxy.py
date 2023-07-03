import re
import time
from enum import Enum
import sys
import asyncio


DISCORD_MENTION_PATTERN = re.compile(r'<@[0-9]+>', re.DOTALL)
SKIP_LATCH_PATTERN = re.compile(r'\\[^\\].*', re.DOTALL)
CLEAR_LATCH_PATTERN = re.compile(r'\\\\.*', re.DOTALL)
DEFAULT_LATCH_MODE = "server"
GLOBAL_STATE_KEY = ''

class AutoproxyMode(Enum):
    Off = 0,
    On = 1,
    Latch_Unlatched = 2
    Latch_Latched = 3

class AutoproxyState:
    def __init__(self, state_key, start_mode, latch_timeout, client):
        self.state_key = state_key
        self.proxy_mode = start_mode or AutoproxyMode.Off
        self.latch_timeout = latch_timeout
        self.clear_task = None
        self.client = client

    async def clear(self):
        try:
            await asyncio.sleep(self.latch_timeout)
        except asyncio.CancelledError:
            return

        if self.proxy_mode == AutoproxyMode.Latch_Latched:
            self.proxy_mode = AutoproxyMode.Latch_Unlatched

        elif self.proxy_mode == AutoproxyMode.On:
            self.proxy_mode = AutoproxyMode.Off

        if self.state_key == GLOBAL_STATE_KEY:
            await self.client.handle_global_autoproxy_change()

    async def start_clear_timer(self):
        await self.cancel_timer()

        self.clear_task = asyncio.create_task(self.clear())

        if self.state_key == GLOBAL_STATE_KEY:
            await self.client.handle_global_autoproxy_change()

    async def cancel_timer(self):
        if self.clear_task is not None:
            self.clear_task.cancel()

        if self.state_key == GLOBAL_STATE_KEY:
            await self.client.handle_global_autoproxy_change()



class AutoproxyManager:
    def __init__(self, client, peer_pattern, latch_scope, latch_timeout, start_enabled):
        if not isinstance(peer_pattern, re.Pattern):
            self.peer_pattern = re.compile(peer_pattern, re.DOTALL)
        else:
            self.peer_pattern = peer_pattern

        self.client = client
        self.states = {}
        self.latch_scope = latch_scope or DEFAULT_LATCH_MODE
        self.latch_timeout = latch_timeout or None

        if start_enabled:
            self.start_mode = AutoproxyMode.Latch_Unlatched
        else:
            self.start_mode = AutoproxyMode.Off

    def _get_autoproxy_state_by_key(self, key):
        if not key in self.states:
            self.states[key] = AutoproxyState(key, self.start_mode, self.latch_timeout, self.client)

        return self.states[key]

    def get_global_state(self):
        state = self._get_autoproxy_state_by_key(GLOBAL_STATE_KEY)

        match state.proxy_mode:
            case AutoproxyMode.Off | AutoproxyMode.Latch_Unlatched:
                return False

            case AutoproxyMode.On | AutoproxyMode.Latch_Latched:
                return True

    def _get_autoproxy_state_key(self, message):
        if self.latch_scope == "global":
            return GLOBAL_STATE_KEY

        if self.latch_scope == 'server':
            return message.guild.id

        if self.latch_scope == 'channel':
            return message.channel.id

    def _get_autoproxy_state_by_message(self, message):
        key = self._get_autoproxy_state_key(message)
        return self._get_autoproxy_state_by_key(key)


    async def handle_command(self, option, message):
        state = self._get_autoproxy_state_by_message(message)

        if option == "off":
            state.proxy_mode = AutoproxyMode.Off

        elif option == "latch":
            state.proxy_mode = AutoproxyMode.Latch_Unlatched

        elif option == self.client.user.mention:
            state.proxy_mode = AutoproxyMode.On
            await state.start_clear_timer()

        elif DISCORD_MENTION_PATTERN.match(option):
            state.proxy_mode = AutoproxyMode.Off

    async def on_manual_proxy(self, message):
        state = self._get_autoproxy_state_by_message(message)

        if state.proxy_mode == AutoproxyMode.Latch_Unlatched or state.proxy_mode == AutoproxyMode.Latch_Latched:
            state.proxy_mode = AutoproxyMode.Latch_Latched
            await state.start_clear_timer()

    async def should_autoproxy(self, message):
        state = self._get_autoproxy_state_by_message(message)

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
                    await state.start_clear_timer()
                    return True

            # When latched, clear if we see a peer's message, otherwise proxy it
            case AutoproxyMode.Latch_Latched:
                if self.peer_pattern.match(message.content) or CLEAR_LATCH_PATTERN.match(message.content):
                    state.proxy_mode = AutoproxyMode.Latch_Unlatched
                    await state.cancel_timer()
                    return False

                await state.start_clear_timer()
                return True

