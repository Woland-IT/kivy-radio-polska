import os
os.environ["KIVY_AUDIO"] = "ffpyplayer"

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.list import MDListItem, MDListItemHeadlineText, MDListItemSupportingText, MDList

from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock

try:
    from pyradios import RadioBrowser
    RADIOBROWSER_AVAILABLE = True
except ImportError:
    RADIOBROWSER_AVAILABLE = False

from ffpyplayer.player import MediaPlayer
import time
from threading import Thread

class RadioScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        main_layout = MDBoxLayout(
            orientation='vertical',
            padding=16,
            spacing=12
        )

        # Wyszukiwanie
        search_box = MDBoxLayout(
            orientation='horizontal',
            spacing=8,
            size_hint_y=None,
            height=56
        )
        self.search_field = MDTextField(
            hint_text="Szukaj stacji (np. RMF, Eska...)",
            mode="outlined",
            size_hint_x=0.75
        )
        search_btn = MDButton(
            MDButtonText(
                text="Szukaj",
            ),
            style="filled",
            on_release=self.on_search
        )
        test_btn = MDButton(
            MDButtonText(
                text="Test RMF FM",
            ),
            style="outlined",
            on_release=self.test_rmf
        )
        search_box.add_widget(self.search_field)
        search_box.add_widget(search_btn)
        search_box.add_widget(test_btn)
        main_layout.add_widget(search_box)

        self.results_label = MDLabel(
            text="Wpisz nazwę stacji i kliknij Szukaj",
            halign="center",
            size_hint_y=None,
            height=48
        )
        main_layout.add_widget(self.results_label)

        self.results_scroll = ScrollView()
        self.results_list = MDList()
        self.results_scroll.add_widget(self.results_list)
        main_layout.add_widget(self.results_scroll)

        player_bar = MDBoxLayout(
            orientation='horizontal',
            spacing=16,
            size_hint_y=None,
            height=80,
            padding=[16, 8, 16, 8]
        )
        self.play_btn = MDIconButton(
            icon="play",
            theme_text_color="Custom",
            text_color=(0, 0.6, 1, 1),
            font_size="48sp",
            on_release=self.toggle_play
        )
        self.stop_btn = MDIconButton(
            icon="stop",
            font_size="48sp",
            on_release=self.stop
        )
        self.status_label = MDLabel(
            text="Nic nie gra",
            halign="center",
            size_hint_x=0.7
        )
        player_bar.add_widget(self.play_btn)
        player_bar.add_widget(self.stop_btn)
        player_bar.add_widget(self.status_label)
        main_layout.add_widget(player_bar)

        self.add_widget(main_layout)

        self.current_sound = None
        self.current_url = None
        self.current_station_name = "?"
        self._should_stop = False

        self.rb = RadioBrowser() if RADIOBROWSER_AVAILABLE else None

        self.__class__.instance = self

    def on_search(self, *args):
        query = self.search_field.text.strip()
        if not query:
            self.results_label.text = "Wpisz nazwę stacji"
            return

        self.results_label.text = f"Wyszukuję: {query}..."
        self.results_list.clear_widgets()

        Clock.schedule_once(lambda dt: self.perform_search(query), 0.2)

    def test_rmf(self, *args):
        url = "http://31.192.216.6:8000/rmf_fm"   # RMF FM – powinno grać
        name = "RMF FM direct"
        self.play_station(url, name)

    def perform_search(self, query):
        if not self.rb:
            self.results_label.text = "Brak pyradios – pip install pyradios"
            return

        try:
            stations = self.rb.search(name=query, country="Poland", limit=20)

            if not stations:
                self.results_label.text = "Nic nie znaleziono"
                return

            self.results_label.text = f"Znaleziono {len(stations)} stacji"

            for station in stations:
                name = station.get("name", "???")
                bitrate = station.get("bitrate", "?")
                url = station.get("url_resolved") or station.get("url", "")
                url = url.split(';')[0].split(';.mp3')[0].rstrip('/')  # usuń typowe śmieci
                
                item = MDListItem(
                    MDListItemHeadlineText(
                        text=name,
                    ),
                    MDListItemSupportingText(
                        text=f"{bitrate} kbps • {url[:60]}...",
                    ),
                    on_release=lambda x, u=url, n=name: self.play_station(u, n)
                )
                self.results_list.add_widget(item)

        except Exception as e:
            self.results_label.text = f"Błąd: {str(e)}"

    def play_station(self, url, name):
        if not url:
            self.status_label.text = "Brak URL"
            return

        self.stop()  # zawsze czyścimy poprzedni

        self.current_url = url
        self.current_station_name = name
        self.status_label.text = f"Ładuję (ffpy): {name}..."
        self._should_stop = False  # reset flagi

        try:
            ff_opts = {
                'vn': True,
                'an': False,
                'sync': 'audio',
                'infbuf': True,
                'framedrop': False,
                'paused': False,
                'volume': 1.0,
                'avioflags': 'direct',
                'probesize': '100000000',      # 100 MB probe
                'analyzeduration': '20000000', # 20 sekund analizy
                'http_persistent': '1',
                'reconnect': '1',
                'reconnect_streamed': '1',
                'fflags': '+discardcorrupt',   # ignoruj uszkodzone pakiety
            }

            player = MediaPlayer(url, ff_opts=ff_opts)

            self.current_sound = player
            self.current_sound_thread = None

            def playback_loop():
                while self.current_sound == player and not self._should_stop:
                    try:
                        frame, val = player.get_frame()
                        if val == 'eof':
                            break
                        if val == 'paused':
                            time.sleep(0.1)
                        elif isinstance(val, float):
                            time.sleep(val)
                        else:
                            time.sleep(0.03)
                    except Exception as inner_e:
                        print(f"Błąd w playback_loop: {inner_e}")
                        Clock.schedule_once(lambda dt: self._on_playback_error(str(inner_e)), 0)
                        break

                # Cleanup
                try:
                    player.close_player()
                except Exception as e:
                    print(f"close_player w wątku: {e}")

                if self.current_sound == player:
                    self.current_sound = None
                    self.current_sound_thread = None

            self.current_sound_thread = Thread(target=playback_loop, daemon=True)
            self.current_sound_thread.start()

            self.play_btn.icon = "pause"
            self.status_label.text = f"Gram: {name}"

        except Exception as e:
            self.status_label.text = f"Błąd ffpy: {str(e)}"
            print(f"ffpyplayer błąd: {e}")

    def _on_playback_error(self, msg):
        self.status_label.text = f"Błąd odtwarzania: {msg[:60]}..."
        self.play_btn.icon = "play"

    def toggle_play(self, *args):
        if not self.current_sound or not hasattr(self.current_sound, 'get_pause'):
            self.status_label.text = "Nic nie jest załadowane"
            return
        paused = self.current_sound.get_pause()
        self.current_sound.set_pause(not paused)
        self.play_btn.icon = "play" if not paused else "pause"
        self.status_label.text = "Pauza" if not paused else f"Gram: {self.current_station_name}"

    def stop(self, *args):
        if self.current_sound:
            self._should_stop = True
            if hasattr(self.current_sound, 'set_pause'):
                self.current_sound.set_pause(True)
        self.play_btn.icon = "play"
        self.status_label.text = "Zatrzymano"

class RadioApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Dark"
        return RadioScreen()

import atexit

def cleanup():
    if hasattr(RadioScreen, 'instance') and RadioScreen.instance.current_sound:
        try:
            RadioScreen.instance.current_sound.close_player()
        except:
            pass

# Zapisz referencję do ekranu
RadioScreen.instance = None

atexit.register(cleanup)

if __name__ == '__main__':
    RadioApp().run()