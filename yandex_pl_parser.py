import argparse
import os
from collections import deque
from pprint import pprint
from threading import Thread
from time import sleep

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from keys import YA_AGENT, YA_KEY, SP_USER
from spoty_constructor import SpotifyUser

options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('log-level=3')

users_for_spoty = deque()


class Track(Thread):

    def __init__(self, collector, line, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.line = line
        self.parent = None
        self.result = None
        self.collector = collector

    def run(self):
        self.parent = self.line.parent.next_sibling.find('a', attrs={'class': "deco-link"})
        try:
            self.collector.update((f'{self.parent.attrs["title"]} ^/& {self.line.attrs["title"]}',))
        except:
            return None


def _ya_auth(driver):
    while True:
        try:
            ya_auth_page = 'https://passport.yandex.ru/auth'
            driver.get(ya_auth_page)
            email = driver.find_element_by_id('passp-field-login')
            email.send_keys(YA_AGENT)
            log_btn = driver.find_element_by_class_name('Button2_view_action')
            log_btn.click()
            sleep(2)
            pwd_field = driver.find_element_by_id('passp-field-passwd')
            pwd_field.send_keys(YA_KEY)
            pwd_btn = driver.find_element_by_class_name('Button2_size_auth-l')
            pwd_btn.click()
            sleep(2)
            return
        except Exception as exc:
            print('Failed yandex authorization')


class Playlist(Thread):

    def __init__(self, pl_url, username, pl_title=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pl_url = pl_url
        self.pl_title = pl_title
        self.username = username
        self.collector = set()
        self.driver = None
        self.done = False

    def run(self):
        page_y = _get_page_y(self.pl_url)
        print(f'page y : {page_y}')
        self.driver = webdriver.Chrome(options=options)
        _ya_auth(self.driver)
        self.driver.get(self.pl_url)
        sleep(4)
        if page_y > 3000:
            self.driver.set_window_size(1000, 3000)
            heights = range(3000, page_y, 5000)
            for scroll_to in heights:
                self.driver.execute_script(f"window.scrollTo(0, {scroll_to});")
                self._eval_rendered_tracks(self.collector)
            else:
                self.driver.execute_script(f"window.scrollTo(0, {page_y - 1000});")
                self._eval_rendered_tracks(self.collector)
        else:
            self.driver.execute_script(f"window.scrollTo(0, {2000});")
            self._eval_rendered_tracks(self.collector)

        self.driver.quit()
        print(self.pl_title, len(self.collector))
        self._save_result()

    def _eval_rendered_tracks(self, collector):
        sleep(3)
        content = self.driver.page_source
        soup = BeautifulSoup(content, features="lxml")
        tracks = [Track(collector, tag) for tag in soup.find_all("div", attrs={"class": "d-track__name"})]
        for track in tracks:
            track.start()
        for track in tracks:
            track.join()

    def _save_result(self):
        valid_filename = ''.join(list(filter(lambda x: x.isalnum() or x in ' ~@#$%^-_(){}\'`', self.pl_title)))
        valid_filename = f'{valid_filename}.txt'
        with open(f'users/{self.username}/{valid_filename}', mode='a', encoding='utf8') as file:
            for value in self.collector:
                file.write(f'{value}\n')
            self.done = True


class User:

    def __init__(self, user_url):
        self.user_url = user_url
        self.ya_url = 'https://music.yandex.ru'
        self.playlists = []
        self.driver = None
        self.username = ''
        self.done = False

    def run(self):
        self.username = self.user_url.split("/")[-1]
        os.makedirs(f'users/{self.username}', exist_ok=True)
        playlists_url = f'{self.user_url}/playlists/'
        self.driver = webdriver.Chrome(options=options)
        _ya_auth(self.driver)
        self.driver.get(playlists_url)
        sleep(3)
        content = self.driver.page_source
        self.driver.quit()
        soup = BeautifulSoup(content, features="lxml")
        playlists = soup.find_all("a", attrs={"class": "d-link deco-link playlist__title-cover"})
        titles = soup.find_all("div", attrs={"class": "playlist__title deco-typo typo-main"})
        playlist_links = [tag.attrs["href"] for tag in playlists]
        playlist_titles = [tag.attrs["title"] for tag in titles]
        pprint(playlist_titles)
        pprint(playlist_links)
        attrs_dict = [{'pl_url': f'{self.ya_url}{value[0]}', 'pl_title': value[1], 'username': self.username} for value
                      in
                      zip(playlist_links, playlist_titles)]
        ya_playlists = [Playlist(**items) for items in attrs_dict]

        for pl in ya_playlists:
            pl.start()
        for pl in ya_playlists:
            pl.join()

        while not all([pl.done for pl in ya_playlists]):
            sleep(10)
            continue
        else:
            self.done = True


# To use webdriver.Chrome() you should download the chromedriver
# and place it to the script directory. Or place it wherever you like and
# and specify it's location like webdriver.Chrome('driver/location')
# link for download: https://sites.google.com/a/chromium.org/chromedriver/downloads
# !!! to download correct version - check it in your chrome's options


def _get_page_y(url):
    driver = webdriver.Chrome(options=options)
    _ya_auth(driver)
    driver.get(url)
    sleep(3)
    height = driver.execute_script("return document.documentElement.scrollHeight")
    driver.execute_script(f"window.scrollTo(0, {str(height)});")
    sleep(3)
    driver.quit()
    return height


def _parse_object(url):
    url_values = url.split('/')
    if url_values[-2] == 'playlists':
        response = requests.get(url)
        soup = BeautifulSoup(response.text, features='lxml')
        div = soup.find('div', attrs={'class': 'd-generic-page-head__main-top'})
        title = div.find('h1', attrs={'class': 'page-playlist__title'}).text
        os.makedirs(f'users/{url_values[-3]}', exist_ok=True)
        return Playlist(pl_url=url, username=url_values[-3], pl_title=title)
    elif url_values[-2] == 'users':
        return User(user_url=url)
    else:
        return None


def _process_cmd(args):
    # user_url = 'https://music.yandex.ru/users/sammyjankins'
    p_obj = _parse_object(args.yandex)
    if isinstance(p_obj, (User, Playlist)):
        p_obj.run()
    else:
        print('Got None')
    print('Collecting spotify playlists...')
    spoty_user = SpotifyUser(SP_USER)
    spoty_user.run()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--yandex', action='store', dest='yandex', required=True, help='Yandex profile page')
    args = parser.parse_args()
    _process_cmd(args)


# python yandex_pl_parser.py --yandex https://music.yandex.ru/users/sammyjankins


if __name__ == '__main__':
    main()
