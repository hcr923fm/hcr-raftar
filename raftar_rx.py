# RAFTAR is the Ropey As Fuck TAlkback Resource.
# Copyright (c) 2017 Callum McLean
# Released under the MIT Licence - see LICENSE.md for details.

import logging
import signal
import time
import json
import urllib2

import linphone

class RAFTaRRX:

    def __init__(self, user, passwd, codecs, snd_dev_pb='', snd_dev_cap=''):
        self.running = True
        self.whitelist = self.get_whitelist()
        callbacks = {
            'call_state_changed': self.call_state_changed
        }
        self.codecs = codecs

        logging.basicConfig(level=logging.INFO)
        signal.signal(signal.SIGINT, self.on_sigint)
        linphone.set_log_handler(self.log_handler)

        self.core = linphone.Core.new(callbacks, None, None)
        self.core.max_calls = 1
        self.core.echo_cancellation_enabled = False
        self.core.video_capture_enabled = False
        self.core.video_display_enabled = False
        self.core.stun_server = 'stun.linphone.org'
        self.core.firewall_policy = linphone.FirewallPolicy.PolicyUseIce
        self.core.mic_gain_db = 0.0
        self.core.playback_gain_db = 0.0

        if snd_dev_pb:
            self.core.playback_device = snd_dev_pb
        if snd_dev_cap:
            self.core.capture_device = snd_dev_cap

        # for codec in self.core.audio_codecs:
        #     if codec.mime_type.upper() in self.codecs:
        #         self.core.enable_payload_type(codec, True)
        #         logging.info("Enabled codec: {0}".format(codec.mime_type))
        #     else:
        #         self.core.enable_payload_type(codec, False)
        #         logging.info("Disabled codec: {0}".format(codec.mime_type))

        self.configure_sip_account(user, passwd)

    def on_sigint(self, signal, frame):
        self.core.terminate_all_calls()
        self.running = False

    def log_handler(self, level, msg):
        method = getattr(logging, level)
        method(msg)

    def call_state_changed(self, core, call, state, message):
        if state == linphone.CallState.IncomingReceived:
            incoming_uri = call.remote_address.as_string_uri_only()
            logging.info("Incoming call from {0}".format(incoming_uri))
            if call.remote_address.as_string_uri_only() in self.whitelist:
                params = core.create_call_params(call)
#				params.record_file = "/home/pi/recording_{0}.wav".format(time.strftime("%y-%m-%d %H%M%S"))
                params.audio_bandwidth_limit = 128
                core.accept_call_with_params(call, params)
#				call.start_recording()
                logging.info("Call accepted")
            else:
                core.decline_call(call, linphone.Reason.Declined)
                logging.info("Call declined: caller not in whitelist")
                chat_room = core.get_chat_room_from_uri(self.whitelist[0])
                msg = chat_room.create_message(
                    call.remote_address_as_string + ' tried to call')
                chat_room.send_chat_message(msg)
            if state == linphone.CallState.Connected:
                logging.info("Call connected. Using codec {0}".format(call.used_audio_codec))

    def configure_sip_account(self, username, password):
        proxy_cfg = self.core.create_proxy_config()
        addr = linphone.Address.new(
            "sip:{0}@sip.linphone.org".format(username))
        proxy_cfg.identity_address = addr
        proxy_cfg.server_addr = "sip:sip.linphone.org;transport=tls"
        proxy_cfg.register_enabled = True
        self.core.add_proxy_config(proxy_cfg)
        auth_info = self.core.create_auth_info(
            username, None, password, None, None, 'sip.linphone.org')
        self.core.add_auth_info(auth_info)

    def get_whitelist(self):
        logging.info("Getting updated whitelist")
        try:
            resp = urllib2.urlopen(
                "https://raw.githubusercontent.com/calmcl1/hcr-raftar/master/whitelist")
            body = resp.read()
            whitelist = json.loads(body)["whitelist"]
            for w in whitelist:
                logging.debug("Added to whitelist: {0}".format(w))

            return whitelist

        except urllib2.URLError, e:
            logging.error("Failed to fetch whitelist: {0}".format(e.reason))

    def run(self):
        while self.running:
            self.core.iterate()
            time.sleep(0.03)