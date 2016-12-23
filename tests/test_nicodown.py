# coding: UTF-8
import os
import random
import shutil

import pytest

import nicotools
from nicotools.nicodown import Video, Comment, Thumbnail, get_infos
from nicotools import utils

SAVE_DIR_1 = "tests/downloads/"
SAVE_DIR_2 = "tests/aaaaa"
OUTPUT = "tests/downloads/info.xml"
INPUT = "tests/ids.txt"

# "N" は一般会員の認証情報、 "P" はプレミアム会員の認証情報
AUTH_N = (os.getenv("addr_n"), os.getenv("pass_n"))
AUTH_P = (os.getenv("addr_p"), os.getenv("pass_p"))

# "nm11028783 sm7174241 ... so8999636" のリスト
VIDEO_ID = list({
    "nm11028783": "[オリジナル曲] august [初音ミク]",
    "sm7174241": "【ピアノ楽譜】 Windows 起動音 [Win3.1 ～ Vista]",
    "sm12169079": "【初音ミク】なでなで【オリジナル】",
    "sm28492584": "【60fps】ぬるぬるフロッピーに入る ご注文はうさぎですか？OP",
    "sm30134391": "音声込みで26KBに圧縮されたスズメバチに刺されるゆうさく",
    "so8999636": "【初音ミク】「Story」 １９’s Sound Factory",
    "watch/1278053154": "「カラフル×メロディ」　オリジナル曲　vo.初音ミク＆鏡音リン【Project DIVA 2nd】",
    "http://www.nicovideo.jp/watch/1341499584": "【sasakure.UK×DECO*27】39【Music Video】",
})

LOGGER = utils.NTLogger(log_level=10)


def rand(num: int=1):
    if num == 0:
        return VIDEO_ID
    else:
        return random.sample(VIDEO_ID, num)


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
        paths = [utils.make_dir(name) for name in save_dir]
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
                with pytest.raises(NameError):
                    utils.make_dir(name)
        else:
            with pytest.raises(NameError):
                utils.make_dir("/{}/downloads".format(__name__))


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


class TestNicodown:
    def param(self, cond, **kwargs):
        cond = "download -l {_mail} -p {_pass} -d {save_dir} " + cond
        params = {"_mail": AUTH_N[0], "_pass": AUTH_N[1],
                  "save_dir": SAVE_DIR_1, "video_id": " ".join(VIDEO_ID)}
        params.update(kwargs)
        return cond.format(**params).split(" ")

    def test_getthumbinfo_to_file_with_nonexist_id(self):
        c = "-i -o " + OUTPUT + " sm1 {video_id}"
        assert nicotools.main(self.param(c))

    def test_getthumbinfo_on_screen(self):
        c = "-i {video_id}"
        assert nicotools.main(self.param(c))

    def test_video(self):
        c = "-v {video_id}"
        nicotools.main(self.param(c, video_id=rand()[0]))

    def test_thumbnail(self):
        c = "-t {video_id}"
        nicotools.main(self.param(c))

    def test_other_directory(self):
        c = "-c {video_id}"
        nicotools.main(self.param(c, save_dir=SAVE_DIR_2))

    def test_comment_thumbnail_1(self):
        c = "-ct {video_id}"
        nicotools.main(self.param(c))

    def test_comment_thumbnail_2(self):
        c = "-ct +" + INPUT
        nicotools.main(self.param(c))

    def test_comment_in_xml(self):
        c = "-cx {video_id}"
        nicotools.main(self.param(c))


class TestNicodownError:
    def param(self, cond, **kwargs):
        cond = "download -l {_mail} -p {_pass} -d {save_dir} " + cond
        params = {"_mail"   : AUTH_N[0], "_pass": AUTH_N[1],
                  "save_dir": SAVE_DIR_1, "video_id": " ".join(VIDEO_ID)}
        params.update(kwargs)
        return cond.format(**params).split(" ")

    def test_without_commands(self):
        with pytest.raises(SystemExit):
            c = "{video_id}"
            nicotools.main(self.param(c))

    def test_invalid_directory_on_windows(self):
        if os.name == "nt":
            c = "-c {video_id}"
            with pytest.raises(NameError):
                nicotools.main(self.param(c, save_dir="nul"))

    def test_no_args(self):
        with pytest.raises(SystemExit):
            nicotools.main()

    def test_one_arg(self):
        with pytest.raises(SystemExit):
            nicotools.main(["download"])

    def test_what_command(self):
        with pytest.raises(SystemExit):
            nicotools.main(["download", "-c", "sm9", "-w"])

    def test_invalid_videoid(self):
        with pytest.raises(SystemExit):
            nicotools.main(["download", "-c", "sm9", "hello"])


class TestComment:
    def test_comment_single(self):
        db = get_infos(rand()[0], LOGGER)
        assert Comment(AUTH_N[0], AUTH_N[1], LOGGER).start(db, SAVE_DIR_1)

    def test_comment_multi(self):
        db = get_infos(rand(0), LOGGER)
        assert Comment(AUTH_N[0], AUTH_N[1], LOGGER).start(db, SAVE_DIR_1, xml=True)

    def test_comment_without_directory(self):
        db = get_infos(rand()[0], LOGGER)
        with pytest.raises(utils.MylistArgumentError):
            # noinspection PyTypeChecker
            Comment(AUTH_N[0], AUTH_N[1], LOGGER).start(db, None)


class TestThumb:
    def test_thumbnail_single(self):
        db = get_infos(rand())
        assert Thumbnail(LOGGER).start(db, SAVE_DIR_1)

    def test_thumbnail_multi(self):
        db = get_infos(rand(0))
        assert Thumbnail(LOGGER).start(db, SAVE_DIR_1)

    def test_thumbnail_without_logger(self):
        db = get_infos(rand(0))
        assert Thumbnail().start(db, SAVE_DIR_1)


class TestVideo:
    def test_video_normal_single(self):
        db = get_infos(rand()[0], LOGGER)
        assert Video(AUTH_N[0], AUTH_N[1], LOGGER).start(db, SAVE_DIR_1)

    def test_video_premium_multi(self):
        db = get_infos(rand(3), LOGGER)
        assert Video(AUTH_P[0], AUTH_P[1], LOGGER).start(db, SAVE_DIR_1)


def test_okatadsuke():
    for _parh in (SAVE_DIR_1, SAVE_DIR_2):
        shutil.rmtree(str(utils.make_dir(_parh)))
