import os
from collections import defaultdict
from time import sleep

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from keys import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, APP_USERNAME


# guide to get spotify client_id and secret:
# https://developer.spotify.com/documentation/general/guides/app-settings/

def valid_naming(line):
    return ''.join(list(filter(lambda x: x.isalnum() or x not in ';:~@#$%^-_…(){}.,\'`', line)))


def do_spoty_object():
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(client_id=CLIENT_ID,
                                  client_secret=CLIENT_SECRET,
                                  redirect_uri=REDIRECT_URI,
                                  username=APP_USERNAME,
                                  scope='user-library-read playlist-modify-public',
                                  ))


class SpPlaylist:

    def __init__(self, filename, directory, spoty_obj):
        self.filename = filename
        self.directory = directory
        self.spoty_obj = spoty_obj
        self.track_links = []
        self.not_found = []
        self.pl_link = ''
        self.pl_title = ''

    def get_track_list(self):
        with open(f'{self.directory}{self.filename}', mode='r', encoding='utf8') as track_list:
            return [line[:-1] for line in track_list]

    def scan(self, list_to_scan):
        for line in list_to_scan:
            artist, title = line.split(' ^/& ')
            if 'из' in title:
                title = title.split('из')[0]
            result = self.spoty_obj.search(f'{artist} {title}')['tracks']['items']
            if not result:
                result = self.spoty_obj.search(f'{artist} {valid_naming(title)}')['tracks']['items']
            if result:
                for position in result:
                    search_title = valid_naming(position['name'])
                    condition_1 = artist.casefold() == position['artists'][0]['name'].casefold()
                    condition_2 = valid_naming(title).casefold() == search_title.casefold()
                    condition_3 = title.casefold() in position['name'].casefold()
                    condition_4 = sorted(valid_naming(title).casefold().split()) == sorted(
                        search_title.casefold().split())
                    condition_5 = valid_naming(title).casefold() in search_title.casefold()
                    condition_6 = search_title.casefold() in valid_naming(title).casefold()
                    condition_7 = len(
                        set(valid_naming(title).casefold().split()) & set(search_title.casefold().split())) >= 2
                    if any((condition_1, condition_2, condition_3,
                            condition_4, condition_5, condition_6, condition_7)):
                        self.track_links.append(position['uri'])
                        break
            else:
                print(f"Can't find track on Spotify: {artist} - {title}")
                self.not_found.append(line)

    def run(self):
        self.pl_title = self.filename.split('.')[0]
        track_list = self.get_track_list()
        self.scan(track_list)
        if not self.track_links:
            self.pl_link = None
            print(f"Didn't find any track for '{self.pl_title}'")
            return
        playlist = None
        while True:
            try:
                playlist = self.spoty_obj.user_playlist_create(APP_USERNAME, self.pl_title)
                break
            except spotipy.SpotifyException:
                sleep(1)
                continue
        self.pl_link = playlist['external_urls']['spotify']
        while len(self.track_links) > 100:
            try:
                self.spoty_obj.user_playlist_add_tracks(APP_USERNAME, playlist['id'], self.track_links[-100:])
                self.track_links = self.track_links[:-100]
            except Exception:
                sleep(1)
                continue
        self.spoty_obj.user_playlist_add_tracks(APP_USERNAME, playlist['id'], self.track_links)
        self.spoty_obj.user_playlist_unfollow(APP_USERNAME, playlist['id'])
        print(f'Tracks missed: {len(self.not_found)}')


class SpotifyUser:
    def __init__(self, user_name):
        self.username = user_name
        self.directory = ''
        self.track_links = []
        self.not_found = defaultdict(list)
        self.pl_links = dict()
        self.spotify = None

    def run(self):
        self.spotify = do_spoty_object()
        self.directory = f'users/{self.username}/'
        sp_playlists = [SpPlaylist(filename=filename, directory=self.directory,
                                   spoty_obj=self.spotify) for filename in os.listdir(self.directory)]
        for pl in sp_playlists:
            pl.run()
        for pl in sp_playlists:
            print(f'Playlist: {pl.pl_title}, URL: {pl.pl_link}')


if __name__ == '__main__':
    pass
