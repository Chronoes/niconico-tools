# coding: UTF-8
import os
import random
import shutil
import time

import aiohttp
import pytest

import nicotools
from nicotools import utils
from nicotools.download import Info, Video, Comment, Thumbnail

Waiting = 5
SAVE_DIR = "tests/downloads/"

# "N" は一般会員の認証情報、 "P" はプレミアム会員の認証情報
AUTH_N = (os.getenv("addr_n"), os.getenv("pass_n"))
AUTH_P = (os.getenv("addr_p"), os.getenv("pass_p"))
LOGGER = utils.NTLogger(log_level=10)


def rand(num=1):
    """
    動画IDをランダムに取り出す。0を指定すると全てを返す。

    "nm11028783 sm7174241 ... so8999636" のリスト
    :param int num:
    :rtype: list[str]
    """
    video_id = list({
        "nm11028783": "[オリジナル曲] august [初音ミク]",
        "sm7174241": "【ピアノ楽譜】 Windows 起動音 [Win3.1 ～ Vista]",
        "sm12169079": "【初音ミク】なでなで【オリジナル】",
        "sm1097445": "【初音ミク】みくみくにしてあげる♪【してやんよ】",
        "sm30134391": "音声込みで26KBに圧縮されたスズメバチに刺されるゆうさく",
        "so8999636": "【初音ミク】「Story」 １９’s Sound Factory",
        "watch/1278053154": "「カラフル×メロディ」　オリジナル曲　vo.初音ミク＆鏡音リン【Project DIVA 2nd】",
        "http://www.nicovideo.jp/watch/1341499584": "【sasakure.UK×DECO*27】39【Music Video】",
    })

    if num == 0:
        return video_id
    else:
        return random.sample(video_id, num)


class TestUtils:
    def test_get_encoding(self):
        assert utils.get_encoding()

    def test_validator(self):
        assert utils.validator(["*", "sm9", "-d"]) == []
        assert (set(utils.validator(
            ["*", " http://www.nicovideo.jp/watch/1341499584",
             " sm1234 ", "watch/sm123456",
             " nm1234 ", "watch/nm123456",
             " so1234 ", "watch/so123456",
             " 123456 ", "watch/1278053154"])) ==
            {"*", "1341499584",
             "sm1234", "sm123456",
             "nm1234", "nm123456",
             "so1234", "so123456",
             "123456", "1278053154"})

    def test_make_dir(self):
        save_dir = ["test", "foo", "foo/bar", "some/thing/text.txt"]
        paths = [utils.get_dir(name) for name in save_dir]
        try:
            for participant, result in zip(save_dir, paths):
                assert str(result).replace("\\", "/").replace("//", "/").endswith(participant)
        finally:
            try:
                for _parh in {item.split("/")[0] for item in save_dir}:
                    shutil.rmtree(_parh)
            except FileNotFoundError:
                pass


class TestUtilsError:
    def test_logger(self):
        with pytest.raises(ValueError):
            # noinspection PyTypeChecker
            utils.NTLogger(log_level=None)

    def test_make_dir(self):
        if os.name == "nt":
            save_dir = ["con", ":"]
            for name in save_dir:
                with pytest.raises(SystemExit):
                    utils.get_dir(name)
        else:
            with pytest.raises(SystemExit):
                utils.get_dir("/{}/downloads".format(__name__))


class TestLogin:
    def test_login_1(self):
        if AUTH_P[0] is not None:
            _ = utils.LogIn(*AUTH_P).session
            sess = utils.LogIn().session
            assert utils.LogIn(*AUTH_N, session=sess).is_login is True

    def test_login_2(self):
        if AUTH_P[0] is not None:
            sess = utils.LogIn(*AUTH_P).session
            assert "-" in utils.LogIn(None, None, session=sess).token

    def test_login_3(self):
        assert "-" in utils.LogIn(*AUTH_N).token


class TestDownload:
    def make_param(self, cond, **kwargs):
        cond = "download --nomulti -l {_mail} -p {_pass} -d {save_dir} --loglevel DEBUG " + cond
        params = {"_mail"   : AUTH_N[0], "_pass": AUTH_N[1],
                  "save_dir": SAVE_DIR, "video_id": rand(1)[0]}
        params.update(kwargs)
        time.sleep(1)
        return cond.format(**params).split(" ")

    def test_video_smile(self):
        cond = "--smile -v {video_id}"
        assert nicotools.main(self.make_param(cond))

    def test_video_dmc(self):
        cond = "-v {video_id}"
        assert nicotools.main(self.make_param(cond))

    def test_sleep_1(self):
        # アクセス制限回避のためすこし待つ
        time.sleep(Waiting)

    def test_video_smile_more(self):
        cond = "--smile --limit 10 -v {video_id}"
        assert nicotools.main(self.make_param(cond))

    def test_video_dmc_more(self):
        cond = "--limit 10 -v {video_id}"
        assert nicotools.main(self.make_param(cond))


class TestDownloadError:
    def make_param(self, cond, **kwargs):
        arg = cond
        if isinstance(cond, str):
            cond = "download -l {_mail} -p {_pass} -d {save_dir} --loglevel DEBUG " + cond
            params = {"_mail"   : AUTH_N[0], "_pass": AUTH_N[1],
                      "save_dir": SAVE_DIR, "video_id": " ".join(rand(0))}
            params.update(kwargs)
            arg = cond.format(**params).split(" ")
        return arg

    def test_without_commands(self):
        with pytest.raises(SystemExit):
            nicotools.main(self.make_param("{video_id}"))

    def test_invalid_directory_on_windows(self):
        if os.name == "nt":
            with pytest.raises(SystemExit):
                nicotools.main(self.make_param("-c {video_id}", save_dir="nul"))

    def test_no_args(self):
        with pytest.raises(SystemExit):
            nicotools.main(self.make_param(cond=None))

    def test_one_arg(self):
        with pytest.raises(SystemExit):
            nicotools.main(self.make_param(["download"]))

    def test_what_command(self):
        with pytest.raises(SystemExit):
            nicotools.main(self.make_param(["download", "-c", "sm9", "-w"]))

    def test_invalid_videoid(self):
        with pytest.raises(SystemExit):
            nicotools.main(self.make_param(["download", "-c", "sm9", "hello"]))

    def test_notexisting(self):
        cond = "-v {video_id}"
        assert nicotools.main(self.make_param(cond, video_id="sm3"))


class TestThumbnail:
    def test_thumbnail_single(self):
        try:
            db = Info(rand(), mail=AUTH_N[0], password=AUTH_N[1], logger=LOGGER).info
            assert Thumbnail(db, save_dir=SAVE_DIR).start()
        except aiohttp.client_exceptions.ClientError:
            pass

    def test_thumbnail_multi(self):
        try:
            db = Info(rand(0), AUTH_N[0], AUTH_N[1], logger=LOGGER).info
            assert Thumbnail(db, save_dir=SAVE_DIR).start()
        except aiohttp.client_exceptions.ClientError:
            pass


class TestComment:
    def test_comment_single(self):
        try:
            db = Info(rand(), mail=AUTH_N[0], password=AUTH_N[1], logger=LOGGER).info
            assert Comment(db, save_dir=SAVE_DIR).start()
        except aiohttp.client_exceptions.ClientError:
            pass

    def test_comment_multi(self):
        try:
            db = Info(rand(), mail=AUTH_N[0], password=AUTH_N[1], logger=LOGGER).info
            assert Comment(db, save_dir=SAVE_DIR, xml=True).start()
        except aiohttp.client_exceptions.ClientError:
            pass


class TestVideo:
    def test_sleep(self):
        # アクセス制限回避のためすこし待つ
        time.sleep(Waiting)

    def test_video_normal_single(self):
        try:
            db = Info(rand(), mail=AUTH_N[0], password=AUTH_N[1], logger=LOGGER).info
            assert Video(db, save_dir=SAVE_DIR, multiline=False).start()
        except aiohttp.client_exceptions.ClientError:
            pass

    def test_video_premium_multi(self):
        if AUTH_P[0] is not None:
            try:
                db = Info(rand(3), mail=AUTH_P[0], password=AUTH_P[1], logger=LOGGER).info
                assert Video(db, save_dir=SAVE_DIR, multiline=False).start()
            except aiohttp.client_exceptions.ClientError:
                pass


def test_okatadsuke():
    shutil.rmtree(str(utils.get_dir(SAVE_DIR)))
