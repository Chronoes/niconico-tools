# coding: utf-8
import argparse
import html
import os
import time
from abc import ABCMeta, abstractmethod
from sys import exit, argv, stderr, stdout
from urllib.parse import unquote
from xml.etree import ElementTree
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
try:
    import progressbar
except ImportError:
    progressbar = None

from utility_func import Msg, URL, Key, MyLogger, LogIn, get_encoding, validator, Err

"""
使い方:

    nicodown --thumbnail --dest ".\Downloads" sm1 sm2 sm3 sm4 sm5
    nicodown --comment --video --thumbnail --dest ".\Downloads" sm1 sm2 sm3 sm4 sm5
    nicodown -cvt -d ".\Downloads" +ids.txt
    nicodown -cvt --xml -dest ".\Downloads" sm1

他のコマンド:
    引数がどの様に解釈されるかを確認したいとき (確認するだけで、プログラムは実行しません):
        nicodown.py --getthumbinfo sm12345678 --out ../file.txt --what

    ログ出力の詳細さを変える:
        nicodown --loglevel WARNING  # エラー以外表示しない
"""


def print_info(queue, file_name=None):
    """
    GetThumbInfo にアクセスして返ってきたXMLをそのまま表示する。

    :param list queue:
    :param typing.Optional[str] file_name:
    :return:
    """
    text = "\n\n".join([requests.get(URL.URL_Info + video_id).text for video_id in queue])
    if file_name:
        with open(file_name, encoding="utf-8", mode="w") as fd:
            fd.write(text + "\n")
    else:
        print(text.encode(get_encoding(), Msg.BACKSLASH).decode(get_encoding()))


def get_infos(queue, logger=None):
    """
    getthumbinfo APIから、細かな情報をもらってくる

    * comment_num       int
    * description       str
    * embeddable        int     # 0 or 1
    * file_name         str
    * first_retrieve    str     # 例えば: 2014-07-26 (もともとは: 2014-07-26T19:27:07+09:00)
    * last_res_body     str
    * length            str
    * length_seconds    int
    * mylist_counter    int
    * movie_type        str     # いずれか: mp4, flv, swf
    * no_live_play      int     # 0 or 1
    * size_high         int
    * size_low          int
    * tags              str
    * tags_list         list
    * thumbnail_url     str
    * title             str
    * user_id           int
    * user_name         str
    * user_icon_url     str
    * video_id          str
    * view_counter      int

    :param list[str] queue: 動画IDのリスト
    :param typing.Optional[MyLogger] logger: ログ出力
    :rtype: dict[str, dict[str, typing.Union[int, str, list]]]
    """
    if logger: logger.info(Msg.nd_start_download.format(len(queue)))

    # データベースとして使うための辞書。削除や非公開の動画はここに入る
    lexikon = {}
    for video_id in queue:
        xmldata = requests.get(URL.URL_Info + video_id).text
        root = ElementTree.fromstring(xmldata)
        # 「status="ok"」 なら動画は生存 / 存在しない動画には「status="fail"」が返る
        if not root.get("status").lower() == "ok":
            if logger: logger.warning(Msg.nd_deleted_or_private.format(video_id))
            else: print(Msg.nd_deleted_or_private.format(video_id))
            continue
        else:
            # 各種情報を辞書に追加していく
            pocket = {}
            # document == "thumb" タグ
            document = root[0]  # type: ElementTree.Element
            finder = document.find

            # 日本語以外のタグが設定されている場合にそれらも巻き込む
            tag_list = [tagstr.text for tagstr in document.iter("tag")]
            # 「分:秒」形式を秒数に直すため分離する
            minute, second = finder(Key.LENGTH).text.split(":")

            pocket[Key.COMMENT_NUM]     = int(finder(Key.COMMENT_NUM).text)
            pocket[Key.DESCRIPTION]     = html.unescape(finder(Key.DESCRIPTION).text)
            pocket[Key.EMBEDDABLE]      = int(finder(Key.EMBEDDABLE).text)
            pocket[Key.FILE_NAME]       = t2filename(finder(Key.TITLE).text)
            pocket[Key.FIRST_RETRIEVE]  = finder(Key.FIRST_RETRIEVE).text[:10]
            pocket[Key.LAST_RES_BODY]   = finder(Key.LAST_RES_BODY).text
            pocket[Key.LENGTH]          = "{}:{}".format(minute, second)
            pocket[Key.LENGTH_SECONDS]  = int(minute) * 60 + int(second)
            pocket[Key.MYLIST_COUNTER]  = int(finder(Key.MYLIST_COUNTER).text)
            pocket[Key.MOVIE_TYPE]      = finder(Key.MOVIE_TYPE).text.lower()
            pocket[Key.NO_LIVE_PLAY]    = int(finder(Key.NO_LIVE_PLAY).text)
            pocket[Key.SIZE_HIGH]       = int(finder(Key.SIZE_HIGH).text)
            pocket[Key.SIZE_LOW]        = int(finder(Key.SIZE_LOW).text)
            pocket[Key.TAGS]            = html.unescape(", ".join(tag_list))  # type: str
            pocket[Key.TAGS_LIST]       = tag_list  # type: list
            pocket[Key.THUMBNAIL_URL]   = finder(Key.THUMBNAIL_URL).text
            pocket[Key.TITLE]           = html.unescape(finder(Key.TITLE).text)
            pocket[Key.VIDEO_ID]        = video_id
            pocket[Key.VIEW_COUNTER]    = int(finder(Key.VIEW_COUNTER).text)
            if video_id.startswith(("sm", "nm")):
                pocket[Key.USER_ID]         = int(finder(Key.USER_ID).text)
                pocket[Key.USER_NAME]       = html.unescape(finder(Key.USER_NAME).text)
                pocket[Key.USER_ICON_URL]   = finder(Key.USER_ICON_URL).text
            else:
                pocket[Key.CH_ID]           = int(finder(Key.CH_ID).text)
                pocket[Key.CH_NAME]         = html.unescape(finder(Key.CH_NAME).text)
                pocket[Key.CH_ICON_URL]     = finder(Key.CH_ICON_URL).text
            lexikon[video_id]               = pocket
    return lexikon


def t2filename(text):
    """
    ファイル名に使えない文字を全角文字に置き換える。

    :param str text: ファイル名
    :rtype: str
    """
    mydic = {
        r"\/": "／", "/": "／", "'": "’", "\"": "”",
        "<": "＜", ">": "＞", "|": "｜", ":": "：",
        "*": "＊", "?": "？", "~": "～", "\\": "＼"
    }
    for item in mydic.keys():
        text = text.replace(item, mydic[item])
    # 置き換えるペアが増えたらこっちを使うと楽かもしれない
    # pattern = re.compile("|".join(re.escape(key) for key in mydic.keys()))
    # return pattern.sub(lambda x: mydic[x.group()], text)
    return text


class GetResources(LogIn, metaclass=ABCMeta):
    def __init__(self, auth, session, logger):
        """
        :param typing.Optional[tuple] auth:
        :param typing.Optional[requests.Session] session:
        :param typing.Optional[MyLogger] logger:
        """
        super().__init__(auth=auth, session=session, logger=logger)
        self.database = None
        self.save_dir = None
        self.logger = logger if logger else self.AltLogger()
        if not hasattr(logger, "handlers"):
            self.logger = self.AltLogger()
        self.session = session

    class AltLogger:
        def emitter(self, text, err=False, en=get_encoding()):
            print(text.encode(en, Msg.BACKSLASH).decode(en),
                  file=[stdout, stderr][err])

        def debug(self, text):    self.emitter(text)

        def info(self, text):     self.emitter(text)

        def error(self, text):    self.emitter(text, True)

        def warning(self, text):  self.emitter(text, True)

        def critical(self, text): self.emitter(text, True)

    def make_dir(self, directory):
        """
        保存場所に指定されたフォルダーがない場合につくる。

        :param str directory: フォルダー名
        """
        if not os.path.isdir(directory):
            os.makedirs(directory)

    @abstractmethod
    def start(self, database, save_dir):
        """

        :param dict[str, dict[str, typing.Union[int, str]]] database:
        :param str save_dir:
        """
        pass

    @abstractmethod
    def download(self, video_id, save_dir):
        """
        :param str save_dir:
        :param str video_id:
        """
        pass


class GetVideos(GetResources):
    def __init__(self, auth=(None, None), session=None, logger=None):
        """
        インスタンス変数 so_video_id は動画IDが so で始まる場合(つまり
        公式チャンネルの動画)にのみ使用する。一時的にso**** のIDを
        保持しておき、ファイル名につけるのに使う。そうしないと
        リダイレクトされた先の「スレッドID」の数字が名前になってしまう。

        :param MyLogger logger:
        :param requests.Session session:
        """
        super().__init__(auth=auth, session=session, logger=logger)
        if progressbar is None:
            self.widgets = None
        else:
            self.widgets = [
                progressbar.Percentage(),
                ' ', progressbar.Bar(),
                ' ', progressbar.ETA(),
                ' ', progressbar.AdaptiveTransferSpeed(),
            ]
        self.so_video_id = None  # type: str

    def start(self, database, save_dir):
        """

        :param dict[str, dict[str, typing.Union[int, str]]] database:
        :param str save_dir:
        """
        if database is None or save_dir is None:
            exit("database and/or directory is not specified")
        self.make_dir(save_dir)
        self.database = database
        self.save_dir = save_dir
        self.logger.info(Msg.nd_start_dl_video.format(len(self.database)))

        for index, video_id in enumerate(self.database.keys()):
            self.logger.info(
                Msg.nd_download_video.format(
                    index + 1, len(database), video_id,
                    self.database[video_id][Key.TITLE]))
            self.download(video_id)
            if len(database) > 1:
                time.sleep(1)

    def download(self, video_id, chunk_size=1024 * 10):
        """
        :param str video_id: 動画ID (e.g. sm1234)
        :param int chunk_size:
        :rtype: bool
        """
        if video_id.startswith("so"):
            redirected = self.session.get(URL.URL_Watch + video_id).url.split("/")[-1]
            self.so_video_id = video_id
            return self.download(redirected)

        response = self.session.get(URL.URL_GetFlv + video_id +
                                    ("", "?as3=1")[video_id.startswith("nm")])

        parameters = response.text.split("&")
        vid_url = [unquote(p[4:]) for p in parameters if p.startswith("url=")][0]
        is_premium = [p[-1] for p in parameters if p.startswith("is_premium=")][0]
        self.logger.debug(Msg.nd_video_url_is.format(video_id, vid_url))

        # 動画視聴ページに行ってCookieをもらってくる
        self.session.get(URL.URL_Watch + video_id)
        # connect timeoutを10秒, read timeoutを30秒に設定
        video_data = self.session.get(url=vid_url, stream=True, timeout=(10.0, 30.0))

        if self.so_video_id:
            file_name = self.make_file_name(self.so_video_id)
            video_id = self.so_video_id
            self.so_video_id = None
        else:
            file_name = self.make_file_name(video_id)

        if is_premium == "1":
            file_size = self.database[video_id][Key.SIZE_HIGH]
        else:
            file_size = self.database[video_id][Key.SIZE_LOW]

        file_path = os.path.join(self.save_dir, file_name)
        if progressbar is None:
            with open(file_path, "wb") as f:
                [f.write(chunk) for chunk in
                 video_data.iter_content(chunk_size=chunk_size) if chunk]
        else:
            pbar = progressbar.ProgressBar(widgets=self.widgets, max_value=file_size)
            pbar.start()
            with open(file_path, "wb") as f:
                downloaded_size = 0
                for chunk in video_data.iter_content(chunk_size=chunk_size):
                    if chunk:
                        downloaded_size += f.write(chunk)
                        pbar.update(downloaded_size)
            pbar.finish()
        self.logger.info(Msg.nd_download_done.format(file_path))
        return True

    def make_file_name(self, video_id):
        return Msg.nd_file_name.format(
            video_id,
            self.database[video_id][Key.FILE_NAME],
            self.database[video_id][Key.MOVIE_TYPE])


class GetThumbnails(GetResources):
    def __init__(self, auth=(None, None), logger=None):
        """
        :param MyLogger logger:
        """
        super().__init__(auth=auth, session=None, logger=logger)

    def start(self, database, save_dir):
        """

        :param dict[str, dict[str, typing.Union[int, str]]] database:
        :param str save_dir:
        """
        self.database = database
        self.make_dir(save_dir)
        self.save_dir = save_dir
        self.logger.info(Msg.nd_start_dl_pict.format(len(self.database)))
        for index, video_id in enumerate(self.database.keys()):
            self.logger.info(
                Msg.nd_download_pict.format(
                    index + 1, len(database), video_id,
                    self.database[video_id][Key.TITLE]))
            self.download(video_id)

    def download(self, video_id):
        """
        :param str video_id: 動画ID (e.g. sm1234)
        :rtype: bool
        """
        image_data = self._download(video_id)
        if not image_data:
            return False
        file_path = os.path.join(self.save_dir, self.make_file_name(video_id))

        with open(file_path, 'wb') as f:
            f.write(image_data.content)
        self.logger.info(Msg.nd_download_done.format(file_path))
        return True

    def _download(self, video_id, is_large=True, retry=1):
        """
        サムネイル画像をダウンロードしにいく。

        :param str video_id: 動画ID (e.g. sm1234)
        :param bool is_large: 大きいサイズのサムネイルを取りに行くかどうか
        :param int retry: 再試行回数
        :rtype: typing.Union[bool, requests.Response]
        """
        with requests.Session() as session:
            # retry設定
            retries = Retry(total=retry,
                            backoff_factor=1,
                            status_forcelist=[500, 502, 503, 504])
            session.mount("http://", HTTPAdapter(max_retries=retries))

            # connect timeoutを10秒, read timeoutを30秒に設定
            response = session.get(url=(self.database[video_id][Key.THUMBNAIL_URL] +
                                        ("", ".L")[is_large]),
                                   timeout=(10.0, 30.0))

            # 大きいサムネイルを求めて404が返ってきたら標準の大きさで試す
            if response.status_code == 404 and is_large:
                return self._download(video_id, is_large=False)
            elif response.ok:
                return response
            else:
                return False

    def make_file_name(self, video_id):
        return Msg.nd_file_name.format(
            video_id, self.database[video_id][Key.FILE_NAME], "jpg")


class GetComments(GetResources):
    def __init__(self, auth=(None, None), session=None, logger=None):
        """
        :param requests.Session session:
        :param MyLogger logger:
        """
        super().__init__(auth=auth, session=session, logger=logger)
        self.so_video_id = None

    def start(self, database, save_dir, xml_mode=False):
        """

        :param bool xml_mode:
        :param dict[str, dict[str, typing.Union[int, str]]] database:
        :param str save_dir:
        """
        self.database = database
        self.make_dir(save_dir)
        self.save_dir = save_dir
        self.logger.info(Msg.nd_start_dl_comment.format(len(self.database)))
        for index, video_id in enumerate(self.database.keys()):
            self.logger.info(
                Msg.nd_download_comment.format(
                    index + 1, len(database), video_id,
                    self.database[video_id][Key.TITLE]))
            self.download(video_id, xml_mode)
            if len(self.database) > 1:
                time.sleep(1.5)

    def download(self, video_id, xml_mode=False):
        """
        :param str video_id: 動画ID (e.g. sm1234)
        :param bool xml_mode:
        :rtype: bool
        """
        if video_id.startswith("so"):
            redirected = self.session.get(URL.URL_Watch + video_id).url.split("/")[-1]
            self.so_video_id = video_id
            return self.download(redirected)

        response = self.session.get(URL.URL_GetFlv + video_id + ("", "?as3=1")[video_id.startswith("nm")])

        if "error=access_locked" in response.text:
            time.sleep(3)
            print("アクセス制限が解除されるのを待っています…")
            time.sleep(3)
            return self.download(video_id)

        parameters = response.text.split("&")
        thread_id = [p[10:] for p in parameters if p.startswith("thread_id=")][0]  # type: str
        msg_server = [unquote(p[3:]) for p in parameters if p.startswith("ms=")][0]  # type:str
        user_id = [p[8:] for p in parameters if p.startswith("user_id=")][0]  # type: str
        user_key = [unquote(p[8:]) for p in parameters if p.startswith("userkey=")][0]  # type: str

        if xml_mode and video_id.startswith(("sm", "nm")):
            comment_data = (self.session.post(url=msg_server, data=self.make_param_xml(thread_id, user_id))
                            .content.replace(b"><", b">\r\n<") + b"\r\n")
        else:
            if video_id.startswith(("sm", "nm")):
                parameters = self.make_param_json(False, user_id, user_key, thread_id)
            else:
                opt_thread_id = [p[19:] for p in parameters if p.startswith("optional_thread_id=")][0]  # type: str
                needs_key = [p[10:] for p in parameters if p.startswith("needs_key=")][0]  # type: str
                thread_key, force_184 = self.get_thread_key(video_id, needs_key)
                parameters = self.make_param_json(
                    True, user_id, user_key, thread_id, opt_thread_id, thread_key, force_184)

            comment_data = (self.session.post(URL.URL_Message_New, json=parameters)
                            .content.replace(b"}, ", b"},\r\n") + b"\r\n")

        file_path = os.path.join(self.save_dir, self.make_file_name(self.so_video_id or video_id, xml_mode))
        self.so_video_id = None
        with open(file_path, "wb") as f:
            f.write(comment_data)
        self.logger.info(Msg.nd_download_done.format(file_path))
        return True

    def make_file_name(self, video_id, xml_mode=False):
        ext = "xml" if xml_mode else "json"
        return Msg.nd_file_name.format(video_id, self.database[video_id][Key.FILE_NAME], ext)

    def get_thread_key(self, video_id, needs_key="1"):
        """

        :param str needs_key:
        :param str video_id:
        :rtype: tuple[str, str]
        """
        if needs_key != "1":
            return "", "0"
        response = self.session.get(URL.URL_GetThreadKey, params={"thread": video_id})
        parameters = response.text.split("&")
        threadkey = [p[10:] for p in parameters if p.startswith("threadkey=")][0]  # type: str
        force_184 = [p[10:] for p in parameters if p.startswith("force_184=")][0]  # type: str
        return threadkey, force_184

    def make_param_xml(self, thread_id, user_id):
        """
        fork="1" があると投稿者コメントを取得する。
        0-99999:9999,1000: 「0分～99999分までの範囲で
        一分間あたり9999件、直近の1000件を取得する」の意味。

        :param str thread_id:
        :param str user_id:
        :rtype: str
        """
        return '<packet>' \
              '<thread thread="{0}" user_id="{1}" version="20090904" scores="1"/>' \
              '<thread thread="{0}" user_id="{1}" version="20090904" scores="1"' \
              ' fork="1" res_from="-1000"/>' \
              '<thread_leaves thread="{0}" user_id="{1}" scores="1">' \
              '0-99999:9999,1000</thread_leaves>' \
              '</packet>'.format(thread_id, user_id)

    def make_param_json(self, official_video, user_id, user_key, thread_id,
                        optional_thread_id=None, thread_key=None, force_184=None):
        """
        fork="1" があると投稿者コメントを取得する。
        0-99999:9999,1000: 「0分～99999分までの範囲で
        一分間あたり9999件、直近の1000件を取得する」の意味。

        :param bool official_video: 公式動画なら True
        :param str user_id:
        :param str user_key:
        :param str thread_id:
        :param str | None optional_thread_id:
        :param str | None thread_key:
        :param str | None force_184:
        """
        result = [
            {"ping": {"content": "rs:0"}},
            {"ping": {"content": "ps:0"}},
            {
                "thread": {
                    "thread"     : optional_thread_id or thread_id,
                    "version"    : "20090904",
                    "language"   : 0,
                    "user_id"    : user_id,
                    "with_global": 1,
                    "scores"     : 1,
                    "nicoru"     : 0,
                    "userkey"    : user_key
                }
            },
            {"ping": {"content": "pf:0"}},
            {"ping": {"content": "ps:1"}},
            {
                "thread_leaves": {
                    "thread"  : optional_thread_id or thread_id,
                    "language": 0,
                    "user_id" : user_id,
                    # "content" : "0-4:100,250",  # 公式仕様のデフォルト値
                    "content" : "0-99999:9999,1000",
                    "scores"  : 1,
                    "nicoru"  : 0,
                    "userkey" : user_key
                }
            },
            {"ping": {"content": "pf:1"}}
        ]

        if official_video:
            result += [{"ping": {"content": "ps:2"}},
                {
                    "thread": {
                        "thread"     : thread_id,
                        "version"    : "20090904",
                        "language"   : 0,
                        "user_id"    : user_id,
                        "force_184"  : force_184,
                        "with_global": 1,
                        "scores"     : 1,
                        "nicoru"     : 0,
                        "threadkey"  : thread_key
                    }
                },
                {"ping": {"content": "pf:2"}},
                {"ping": {"content": "ps:3"}},
                {
                    "thread_leaves": {
                        "thread"   : thread_id,
                        "language" : 0,
                        "user_id"  : user_id,
                        # "content"  : "0-4:100,250",  # 公式仕様のデフォルト値
                        "content"  : "0-99999:9999,1000",
                        "scores"   : 1,
                        "nicoru"   : 0,
                        "force_184": force_184,
                        "threadkey": thread_key
                    }
                },
                {"ping": {"content": "pf:3"}}]
        result += [{"ping": {"content": "rf:0"}}]
        return result


def main(args):
    if args.what:
        print(args)
        exit()

    videoid = validator(args.VIDEO_ID)
    if not videoid:
        exit(Err.invalid_videoid)

    if args.getthumbinfo:
        file_name = args.out[0] if isinstance(args.out, list) else None
        print_info(videoid, file_name)
        exit()
    if not os.path.isdir(args.dest):
        os.makedirs(args.dest)

    logger = MyLogger(log_level=args.loglevel, log_file_name=Msg.LOG_FILE_ND)
    database = get_infos(videoid, logger=logger)

    username = getattr(args, "user")[0] if isinstance(getattr(args, "user"), list) else None
    password = getattr(args, "pass")[0] if isinstance(getattr(args, "pass"), list) else None
    # ログインしてそのセッションを使いまわす
    session = LogIn((username, password), logger=logger).session

    if args.thumbnail:
        GetThumbnails(logger=logger).start(database, args.dest)

    if args.comment:
        GetComments(logger=logger, session=session).start(database, args.dest, args.xml)

    if args.video:
        GetVideos(logger=logger, session=session).start(database, args.dest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(fromfile_prefix_chars="+", description=Msg.nd_description)
    parser.add_argument("VIDEO_ID", nargs="+", type=str, help=Msg.nd_help_video_id)
    parser.add_argument("-u", "--user", nargs=1, help=Msg.nd_help_username, metavar="MAIL")
    parser.add_argument("-p", "--pass", nargs=1, help=Msg.nd_help_password, metavar="PASSWORD")
    parser.add_argument("-d", "--dest", nargs="?", type=str, default=os.getcwd(),
                        help=Msg.nd_help_destination)
    parser.add_argument("-c", "--comment", action="store_true", help=Msg.nd_help_comment)
    parser.add_argument("-v", "--video", action="store_true", help=Msg.nd_help_video)
    parser.add_argument("-t", "--thumbnail", action="store_true", help=Msg.nd_help_thumbnail)
    parser.add_argument("-i", "--getthumbinfo", action="store_true", help=Msg.nd_help_info)
    parser.add_argument("-x", "--xml", action="store_true", help=Msg.nd_help_xml)
    parser.add_argument("-o", "--out", nargs=1, help=Msg.nd_help_outfile, metavar="ファイル名")
    parser.add_argument("-w", "--what", action="store_true", help=Msg.nd_help_what)
    parser.add_argument("-l", "--loglevel", type=str.upper, default="INFO",
                        help=Msg.nd_help_loglevel,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

    if len(argv) == 1:
        parser.print_help()
        exit()
    main(parser.parse_args())
