# coding: utf-8
import html
import os
import socket
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs
from xml.etree import ElementTree

import requests
from requests.exceptions import Timeout
from requests.packages.urllib3.exceptions import TimeoutError, RequestError

try:
    import progressbar
except ImportError:
    progressbar = None

from . import utils
from .utils import Msg, Err, URL, Key, KeyGetFlv

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

IS_DEBUG = int(os.getenv("PYTHON_TEST", "0"))


def print_info(queue, file_name=None):
    """
    GetThumbInfo にアクセスして返ってきたXMLをそのまま表示する。

    :param list queue:
    :param str | Path | None file_name:
    :return: bool
    """
    text = "\n\n".join([requests.get(URL.URL_Info + video_id).text for video_id in queue])
    if file_name:
        file_name = utils.make_dir(file_name)
        with file_name.open(encoding="utf-8", mode="w") as fd:
            fd.write(text + "\n")
    else:
        print(text.encode(utils.get_encoding(), utils.BACKSLASH).decode(utils.get_encoding()))
    return True


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
    * v_or_t_id         str
    * watch_url         str

    :param list[str] queue: 動画IDのリスト
    :param NTLogger | None logger: ログ出力
    :rtype: dict[str, dict[str, int | str | list]]
    """
    if logger: logger.info(Msg.nd_start_download.format(len(queue)))
    else: print(Msg.nd_start_download.format(len(queue)))

    # データベースとして使うための辞書。削除や非公開の動画はここに入る
    lexikon = {}
    for video_id in utils.validator(queue):
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
            pocket[Key.WATCH_URL]       = finder(Key.WATCH_URL).text
            pocket[Key.V_OR_T_ID]       = finder(Key.WATCH_URL).text.split("/")[-1]
            if video_id.startswith(("sm", "nm")):
                pocket[Key.USER_ID]         = int(finder(Key.USER_ID).text)
                pocket[Key.USER_NAME]       = html.unescape(finder(Key.USER_NAME).text)
                pocket[Key.USER_ICON_URL]   = finder(Key.USER_ICON_URL).text
            else:  # so1234 または 123456 の形式
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


class Canopy:
    def __init__(self):
        self.database = None
        self.save_dir = None  # type: Path

    def make_name(self, video_id, ext):
        """
        ファイル名を返す。

        :param str video_id:
        :param str ext:
        :rtype: Path
        """
        utils.check_arg(locals())
        file_name =  Msg.nd_file_name.format(
            video_id, self.database[video_id][Key.FILE_NAME], ext)
        return Path(self.save_dir).resolve() / file_name

    @classmethod
    def get_from_getflv(cls, video_id, session):
        """
        GetFlv APIから情報を得る。

        * GetFlvのサンプル:

        thread_id=1406370428
        &l=314
        &url=http%3A%2F%2Fsmile-pom32.nicovideo.jp%2Fsmile%3Fm%3D24093152.45465
        &ms=http%3A%2F%2Fmsg.nicovideo.jp%2F27%2Fapi%2F
        &ms_sub=http%3A%2F%2Fsub.msg.nicovideo.jp%2F27%2Fapi%2F
        &user_id=<ユーザーIDの数字>
        &is_premium=1
        &nickname=<URLエンコードされたユーザー名の文字列>
        &time=1475176067845
        &done=true
        &ng_rv=220
        &userkey=1475177867.%7E1%7EhPBJrVv78e251OPzyAiSs1fYAJhYIzDPOq5LNiNqZxs

        * 但しアクセス制限がかかったときには:

        error=access_locked&done=true

        :param str video_id:
        :param requests.Session session:
        :rtype: dict[str, str] | None
        """
        utils.check_arg(locals())
        suffix = {"as3": 1} if video_id.startswith("nm") else None
        response = session.get(URL.URL_GetFlv + video_id, params=suffix)
        # self.logger.debug("GetFLV Response: {}".format(response.text))
        return cls.extract_getflv(response.text)

    @classmethod
    def extract_getflv(cls, content):
        """

        :param str content: GetFLV の返事
        :rtype: dict[str, str] | None
        """
        parameters = parse_qs(content)
        if parameters.get("error") is not None:
            return None
        return {
            KeyGetFlv.THREAD_ID    : parameters[KeyGetFlv.THREAD_ID][0],
            KeyGetFlv.LENGTH       : parameters[KeyGetFlv.LENGTH][0],
            KeyGetFlv.VIDEO_URL    : parameters[KeyGetFlv.VIDEO_URL][0],
            KeyGetFlv.MSG_SERVER   : parameters[KeyGetFlv.MSG_SERVER][0],
            KeyGetFlv.MSG_SUB      : parameters[KeyGetFlv.MSG_SUB][0],
            KeyGetFlv.USER_ID      : parameters[KeyGetFlv.USER_ID][0],
            KeyGetFlv.IS_PREMIUM   : parameters[KeyGetFlv.IS_PREMIUM][0],
            KeyGetFlv.NICKNAME     : parameters[KeyGetFlv.NICKNAME][0],
            KeyGetFlv.USER_KEY     : parameters[KeyGetFlv.USER_KEY][0],

            # 以下は公式動画にだけあるもの。通常の動画ではNone
            KeyGetFlv.OPT_THREAD_ID: parameters.get(KeyGetFlv.OPT_THREAD_ID, [None])[0],
            KeyGetFlv.NEEDS_KEY    : parameters.get(KeyGetFlv.NEEDS_KEY, [None])[0],
        }


class GetVideos(utils.LogIn, Canopy):
    def __init__(self, mail=None, password=None, logger=None, session=None):
        """
        動画をダウンロードする。

        :param str | None mail:
        :param str | None password:
        :param NTLogger logger:
        :param requests.Session session:
        """
        super().__init__(mail=mail, password=password, logger=logger, session=session)

    def start(self, database, save_dir):
        """

        :param dict[str, dict[str, int | str]] database:
        :param str | Path save_dir:
        :rtype: bool
        """
        utils.check_arg(locals())
        self.logger.debug("Directory to save in: {}".format(save_dir))
        self.logger.debug("Dictionary of Videos: {}".format(database))
        self.save_dir = utils.make_dir(save_dir)
        self.database = database
        self.logger.info(Msg.nd_start_dl_video.format(len(self.database)))

        for index, video_id in enumerate(self.database.keys()):
            self.logger.info(
                Msg.nd_download_video.format(
                    index + 1, len(database), video_id,
                    self.database[video_id][Key.TITLE]))
            self.download(video_id)
            if len(database) > 1:
                time.sleep(1)
        return True

    def download(self, video_id, chunk_size=1024 * 50):
        """
        :param str video_id: 動画ID (e.g. sm1234)
        :param int chunk_size: 一度にサーバーに要求するファイルサイズ
        :rtype: bool
        """
        utils.check_arg(locals())
        db = self.database[video_id]
        if video_id.startswith("so"):
            redirected = self.session.get(URL.URL_Watch + video_id).url.split("/")[-1]
            db[Key.V_OR_T_ID] = redirected
        self.logger.debug("Video ID and its Thread ID (of officials):"
                          " {}".format(video_id, db[Key.V_OR_T_ID]))

        response = self.get_from_getflv(db[Key.V_OR_T_ID], self.session)

        vid_url = response[KeyGetFlv.VIDEO_URL]
        is_premium = response[KeyGetFlv.IS_PREMIUM]

        # 動画視聴ページに行ってCookieをもらってくる
        self.session.get(URL.URL_Watch + video_id)
        # connect timeoutを10秒, read timeoutを30秒に設定
        # ↓この時点ではダウンロードは始まらず、ヘッダーだけが来ている
        video_data = self.session.get(url=vid_url, stream=True, timeout=(10.0, 30.0))
        file_size = int(video_data.headers["content-length"])
        self.logger.debug("File Size: {} (Premium: {})".format(
            file_size, [False, True][int(is_premium)]))

        return self._saver(video_id, video_data, file_size, chunk_size)

    def _saver(self, video_id, video_data, file_size, chunk_size):
        """

        :param str video_id:
        :param requests.Response video_data: 動画ファイルのURL
        :param int file_size: ファイルサイズ
        :param int chunk_size: 一度にサーバーに要求するファイルサイズ
        :rtype: bool
        """
        file_path = self.make_name(video_id, self.database[video_id][Key.MOVIE_TYPE])
        self.logger.debug("File Path: {}".format(file_path))

        if progressbar is None:
            with file_path.open("wb") as f:
                [f.write(chunk) for chunk in
                 video_data.iter_content(chunk_size=chunk_size) if chunk]
        else:
            widgets = [
                progressbar.Percentage(),
                ' ', progressbar.Bar(),
                ' ', utils.sizeof_fmt(file_size),
                ' ', progressbar.ETA(format="あと: %(eta)s"),
                ' ', progressbar.AdaptiveTransferSpeed(),
            ]
            pbar = progressbar.ProgressBar(widgets=widgets, max_value=file_size)
            pbar.start()
            with file_path.open("wb") as f:
                downloaded_size = 0
                for chunk in video_data.iter_content(chunk_size=chunk_size):
                    if chunk:
                        downloaded_size += f.write(chunk)
                        pbar.update(downloaded_size)
            pbar.finish()
        self.logger.info(Msg.nd_download_done.format(file_path))
        return True


class GetThumbnails(Canopy):
    def __init__(self, logger=None):
        """
        :param NTLogger logger:
        """
        super().__init__()
        self.logger = logger
        if not logger or not hasattr(logger, "handlers"):
            self.logger = utils.NTLogger()

    def start(self, database, save_dir, is_large=True):
        """

        :param dict[str, dict[str, int | str]] database:
        :param str | Path save_dir:
        :param bool is_large: 大きいサムネイルを取りに行くかどうか
        :rtype: bool
        """
        utils.check_arg(locals())
        self.logger.debug("Directory to save in: {}".format(save_dir))
        self.logger.debug("Dictionary of Videos: {}".format(database))
        self.database = database
        self.save_dir = utils.make_dir(save_dir)
        self.logger.info(Msg.nd_start_dl_pict.format(len(self.database)))
        for index, video_id in enumerate(self.database.keys()):
            self.logger.info(
                Msg.nd_download_pict.format(
                    index + 1, len(database), video_id,
                    self.database[video_id][Key.TITLE]))
            self.download(video_id, is_large)
        return True

    def download(self, video_id, is_large=True):
        """
        :param str video_id: 動画ID (e.g. sm1234)
        :param bool is_large: 大きいサムネイルを取りに行くかどうか
        :rtype: bool
        """
        utils.check_arg(locals())
        url = self.database[video_id][Key.THUMBNAIL_URL]
        if is_large:
            url += ".L"
        image_data = self._worker(video_id, url, is_large)
        if not image_data:
            return False
        return self._saver(video_id, image_data)

    def _worker(self, video_id, url, is_large=True):
        """
        サムネイル画像をダウンロードしにいく。

        :param str video_id: 動画ID (e.g. sm1234)
        :param str url: 画像のURL
        :param bool is_large: 大きいサムネイルを取りに行くかどうか
        :rtype: bool | requests.Response
        """
        utils.check_arg(locals())
        with requests.Session() as session:
            try:
                # connect timeoutを5秒, read timeoutを10秒に設定
                response = session.get(url=url, timeout=(5.0, 10.0))
                if response.ok:
                    return response
                # 大きいサムネイルを求めて404が返ってきたら標準の大きさで試す
                if response.status_code == 404:
                    if is_large and url.endswith(".L"):
                        return self._worker(video_id, url[:-2], is_large=False)
                    else:
                        self.logger.error(Err.connection_404.format(
                            video_id, self.database[video_id][Key.TITLE]))
                        return False
            except (TypeError, ConnectionError,
                    socket.timeout, Timeout, TimeoutError, RequestError) as e:
                self.logger.debug("An exception occurred: {}".format(e))
                if is_large and url.endswith(".L"):
                    return self._worker(video_id, url[:-2], is_large=False)
                else:
                    self.logger.error(Err.connection_timeout.format(
                        video_id, self.database[video_id][Key.TITLE]))
                    return False

    def _saver(self, video_id, image_data):
        file_path = self.make_name(video_id, "jpg")
        self.logger.debug("File Path: {}".format(file_path))

        with file_path.open('wb') as f:
            f.write(image_data.content)
        self.logger.info(Msg.nd_download_done.format(file_path))
        return True


class GetComments(utils.LogIn, Canopy):
    def __init__(self, mail=None, password=None, logger=None, session=None):
        """
        :param str | None mail:
        :param str | None password:
        :param NTLogger logger:
        :param requests.Session session:
        """
        super().__init__(mail=mail, password=password, logger=logger, session=session)

    def start(self, database, save_dir, xml=False):
        """

        :param dict[str, dict[str, int | str]] database:
        :param str | Path save_dir:
        :param bool xml:
        """
        utils.check_arg(locals())
        self.logger.debug("Directory to save in: {}".format(save_dir))
        self.logger.debug("Dictionary of Videos: {}".format(database))
        self.logger.debug("Download XML? : {}".format(xml))
        self.database = database
        self.save_dir = utils.make_dir(save_dir)
        self.logger.info(Msg.nd_start_dl_comment.format(len(self.database)))
        for index, video_id in enumerate(self.database.keys()):
            self.logger.info(
                Msg.nd_download_comment.format(
                    index + 1, len(database), video_id,
                    self.database[video_id][Key.TITLE]))
            self.download(video_id, xml)
            if len(self.database) > 1:
                time.sleep(1.5)
        return True

    def download(self, video_id, xml=False):
        """
        :param str video_id: 動画ID (e.g. sm1234)
        :param bool xml:
        :rtype: bool
        """
        utils.check_arg(locals())
        db = self.database[video_id]
        if video_id.startswith("so"):
            redirected = self.session.get(URL.URL_Watch + video_id).url.split("/")[-1]
            db[Key.V_OR_T_ID] = redirected
        self.logger.debug("Video ID and its Thread ID (of officials):"
                          " {}".format(video_id, db[Key.V_OR_T_ID]))

        response = self.get_from_getflv(db[Key.V_OR_T_ID], self.session)

        if response is None:
            time.sleep(4)
            print(Err.waiting_for_permission)
            time.sleep(4)
            return self.download(video_id, xml)

        thread_id = response[KeyGetFlv.THREAD_ID]
        msg_server = response[KeyGetFlv.MSG_SERVER]
        user_id = response[KeyGetFlv.USER_ID]
        user_key = response[KeyGetFlv.USER_KEY]

        opt_thread_id = response[KeyGetFlv.OPT_THREAD_ID]
        needs_key = response[KeyGetFlv.NEEDS_KEY]

        if xml and video_id.startswith(("sm", "nm")):
            req_param = self.make_param_xml(thread_id, user_id)
            self.logger.debug("Posting Parameters: {}".format(req_param))

            res_com = self.session.post(url=msg_server, data=req_param)
            comment_data = res_com.text.replace("><", ">\n<")
        else:
            if video_id.startswith(("sm", "nm")):
                req_param = self.make_param_json(
                    False, user_id, user_key, thread_id)
            else:
                thread_key, force_184 = self.get_thread_key(db[Key.V_OR_T_ID],
                                                            needs_key)
                req_param = self.make_param_json(
                    True, user_id, user_key, thread_id,
                    opt_thread_id, thread_key, force_184)

            self.logger.debug("Posting Parameters: {}".format(req_param))
            res_com = self.session.post(
                url=URL.URL_Message_New,
                json=req_param)
            comment_data = res_com.text.replace("}, ", "},\n")

        comment_data = comment_data.encode(res_com.encoding).decode("utf-8")
        return self._saver(video_id, comment_data, xml)

    def _saver(self, video_id, comment_data, xml):
        """

        :param str video_id:
        :param str comment_data:
        :param bool xml:
        :return:
        """
        utils.check_arg(locals())
        if xml and video_id.startswith(("sm", "nm")):
            extention = "xml"
        else:
            extention = "json"

        file_path = self.make_name(video_id, extention)
        self.logger.debug("File Path: {}".format(file_path))
        with file_path.open("w", encoding="utf-8") as f:
            f.write(comment_data + "\n")
        self.logger.info(Msg.nd_download_done.format(file_path))
        return True

    def get_thread_key(self, video_id, needs_key):
        """
        専用のAPIにアクセスして thread_key を取得する。

        :param str needs_key:
        :param str video_id:
        :rtype: tuple[str, str]
        """
        utils.check_arg(locals())
        if not needs_key == "1":
            self.logger.debug("Video ID (or Thread ID): {},"
                              " needs_key: {}".format(video_id, needs_key))
            return "", "0"
        response = self.session.get(URL.URL_GetThreadKey, params={"thread": video_id})
        self.logger.debug("Response from GetThreadKey API: {}".format(response.text))
        parameters = parse_qs(response.text)
        threadkey = parameters["threadkey"][0]  # type: str
        force_184 = parameters["force_184"][0]  # type: str
        return threadkey, force_184

    def make_param_xml(self, thread_id, user_id):
        """
        コメント取得用のxmlを構成する。

        fork="1" があると投稿者コメントを取得する。
        0-99999:9999,1000: 「0分～99999分までの範囲で
        一分間あたり9999件、直近の1000件を取得する」の意味。

        :param str thread_id:
        :param str user_id:
        :rtype: str
        """
        utils.check_arg(locals())
        self.logger.debug("Arguments: {}".format(locals()))
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
        コメント取得用のjsonを構成する。

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
        utils.check_arg({"official_video": official_video, "user_id": user_id,
                         "user_key": user_key, "thread_id": thread_id})
        self.logger.debug("Arguments of creating JSON: {}".format(locals()))
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
    """
    メイン。

    :param args: ArgumentParser.parse_args() によって解釈された引数
    :rtype: bool
    """
    mailadrs = args.mail[0] if args.mail else None
    password = args.password[0] if args.password else None

    """ エラーの除外 """
    videoid = utils.validator(args.VIDEO_ID)
    if not videoid:
        sys.exit(Err.invalid_videoid)
    if not (args.getthumbinfo or args.thumbnail or args.comment or args.video):
        sys.exit(Err.not_specified.format("--thumbnail、 --comment、 --video のいずれか"))

    if args.getthumbinfo:
        file_name = args.out[0] if isinstance(args.out, list) else None
        return print_info(videoid, file_name)

    """ 本筋 """
    log_level = "DEBUG" if IS_DEBUG else args.loglevel
    logger = utils.NTLogger(log_level=log_level, file_name=utils.LOG_FILE_ND)
    destination = utils.make_dir(args.dest)
    database = get_infos(videoid, logger=logger)

    res_t = False
    if args.thumbnail:
        res_t = GetThumbnails(logger=logger).start(database, destination)
        if not (args.comment or args.video):
            # サムネイルのダウンロードだけならここで終える。
            return res_t

    session = utils.LogIn(mail=mailadrs, password=password, logger=logger).session

    res_c = False
    if args.comment:
        res_c = GetComments(logger=logger, session=session).start(database, destination, args.xml)

    res_v = False
    if args.video:
        res_v = GetVideos(logger=logger, session=session).start(database, destination)

    return res_c | res_v | res_t
