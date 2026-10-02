"""Outbound sendMessage only. No chat polling. Telegram failure is nonfatal."""
import requests
import queue
import threading


class Telegram:
    def __init__(self, token='', chat_id='', transport=None):
        self._token, self._chat_id = token, chat_id
        self._http = transport or requests.Session()
        self._queue = None
        self._worker = None

    def send(self, text):
        if not self._token or not self._chat_id:
            return False
        if self._queue is None:
            self._queue = queue.Queue(maxsize=100)
            self._worker = threading.Thread(target=self._run, daemon=True, name='guardian-telegram')
            self._worker.start()
        try:
            self._queue.put_nowait(text[:4000])
            return True
        except queue.Full:
            return False

    def _run(self):
        while True:
            text = self._queue.get()
            try:
                response = self._http.post('https://api.telegram.org/bot' + self._token + '/sendMessage',
                                           json={'chat_id': self._chat_id, 'text': text},
                                           timeout=(1, 2), allow_redirects=False)
                response.status_code == 200 and response.json().get('ok') is True
            except Exception:
                pass
            finally:
                self._queue.task_done()
