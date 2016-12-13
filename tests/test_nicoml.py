# coding: utf-8
import logging
import os
import pytest
from datetime import datetime

import nicotools
from nicotools import nicoml
from nicotools import utils

SAVE_DIR = "tests/Downloads/"
TEST_LIST = "TEST_LIST" + str(datetime.now()).replace(" ", "_").replace(":", "")
TEST_LIST_TO = "TEST_LIST_TO" + str(datetime.now()).replace(" ", "_").replace(":", "")

# テスト用の一般会員の認証情報
AUTH_N = (os.getenv("addr_n"), os.getenv("pass_n"))

VIDEO_IDS = " ".join(sorted({
    "watch/sm8628149": "【東方】Bad Apple!!　ＰＶ【影絵】",
    "watch/sm9": "新・豪血寺一族 -煩悩解放 - レッツゴー！陰陽師",
    "watch/sm2057168": "M.C.ドナルドはダンスに夢中なのか？最終鬼畜道化師ドナルド・Ｍ",
    "watch/sm22954889": "幕末志士達のスマブラ６４実況プレイ",
    "watch/sm1097445": "【初音ミク】みくみくにしてあげる♪【してやんよ】",
    "watch/sm10780722": "おちゃめ機能　歌った",
    "watch/sm15630734": "『初音ミク』千本桜『オリジナル曲PV』",
    "watch/sm1715919": "初音ミク　が　オリジナル曲を歌ってくれたよ「メルト」",
    "watch/sm9354085": "自演乙",
    "watch/sm6188097": "【マリオ64実況】　奴が来る　伍【幕末志士】",
    "watch/sm2049295": "【 Silver Forest × U.N.オーエンは彼女なのか？ 】 −sweet little sister−",
    "watch/sm500873": "組曲『ニコニコ動画』 "
}))
LIST_ID = 0
LIST_NAME = ""
LIST_ID_TO = 0
LIST_NAME_TO = ""
INSANE_NAME = "🕒🕘🕒🕘"  # 時計の絵文字4つ
INSTANCE = None  # type: nicoml.NicoMyList
LOGGER = utils.NTLogger(file_name=utils.LOG_FILE_ML, log_level=logging.DEBUG)


class TestMla:
    def initialize(self):
        global INSTANCE, LIST_ID, LIST_NAME, LIST_ID_TO, LIST_NAME_TO
        INSTANCE = self.get_instance()
        LIST_ID, LIST_NAME = self.get_id_name(TEST_LIST)
        LIST_ID_TO, LIST_NAME_TO = self.get_id_name(TEST_LIST_TO)

    def get_id_name(self, name):
        result = INSTANCE.get_list_id(name)
        if result.get("error"):
            self.create(name)
            return self.get_id_name(name)
        return result["list_id"], result["list_name"]

    def get_instance(self):
        return nicoml.NicoMyList(AUTH_N[0], AUTH_N[1], logger=LOGGER)

    def create(self, name):
        INSTANCE.create_mylist(name)

    def purge(self, name):
        INSTANCE.purge_mylist(name, True)

    def param(self, cond):
        cond = "mylist -u {_mail} -p {_pass} " + cond
        return cond.format(_mail=AUTH_N[0], _pass=AUTH_N[1]).split(" ")

    def nicoml_add_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --add {}".format(LIST_NAME, VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_add_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --id --add {}".format(LIST_ID, VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_add_3(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --add +ids.txt".format(LIST_NAME)
        assert nicotools.main(self.param(c))

    def nicoml_del_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --delete {}".format(LIST_NAME, VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_del_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --delete * --yes".format(LIST_NAME)
        assert nicotools.main(self.param(c))

    def nicoml_move_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --to {} --move {}".format(LIST_NAME, LIST_NAME_TO, VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_move_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --to {} --move *".format(LIST_NAME, LIST_NAME_TO)
        assert nicotools.main(self.param(c))

    def nicoml_copy_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --to {} --copy {}".format(LIST_NAME_TO, LIST_NAME, VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_copy_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --to {} --copy *".format(LIST_NAME_TO, LIST_NAME)
        assert nicotools.main(self.param(c))

    def test_amcdpr_1(self, caplog):
        caplog.set_level(logging.INFO)
        self.initialize()
        self.nicoml_add_1(caplog)
        self.nicoml_move_1(caplog)
        self.nicoml_copy_1(caplog)
        self.nicoml_del_1(caplog)
        self.test_okatadsuke()

    def test_amcdpr_2(self, caplog):
        caplog.set_level(logging.INFO)
        self.initialize()
        self.nicoml_add_2(caplog)
        self.nicoml_move_2(caplog)
        self.nicoml_copy_2(caplog)
        self.nicoml_del_2(caplog)
        self.test_okatadsuke()

    def nicoml_add_to_deflist(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --add {}".format("とりあえずマイリスト", VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_move_from_deflist(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --to {} --move {}".format("とりあえずマイリスト", LIST_NAME_TO, VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_copy_to_deflist(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --to {} --copy {}".format(LIST_NAME_TO, "とりあえずマイリスト", VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_del_from_deflist(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{} --delete {}".format("とりあえずマイリスト", VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def test_amcdpr_deflist(self, caplog):
        caplog.set_level(logging.INFO)
        self.initialize()
        self.nicoml_add_to_deflist(caplog)
        self.nicoml_move_from_deflist(caplog)
        self.nicoml_copy_to_deflist(caplog)
        INSTANCE.show(utils.ALL_ITEM, survey=True)
        self.nicoml_del_from_deflist(caplog)
        self.test_okatadsuke()

    def test_okatadsuke(self):
        try:
            self.purge(LIST_NAME)
        except utils.MylistNotFoundError:
            pass
        try:
            self.purge(LIST_NAME_TO)
        except utils.MylistNotFoundError:
            pass


class TestMlb:
    def get_id_name(self, name):
        result = INSTANCE.get_list_id(name)
        if result.get("error"):
            INSTANCE.create_mylist(name)
            return self.get_id_name(name)
        return result["list_id"], result["list_name"]

    def param(self, cond):
        cond = "mylist -u {_mail} -p {_pass} " + cond
        return cond.format(_mail=AUTH_N[0], _pass=AUTH_N[1]).split(" ")

    def test_initialize(self):
        global INSTANCE, LIST_ID, LIST_NAME, LIST_ID_TO, LIST_NAME_TO
        INSTANCE = nicoml.NicoMyList(AUTH_N[0], AUTH_N[1], logger=LOGGER)
        LIST_ID, LIST_NAME = self.get_id_name(TEST_LIST)
        LIST_ID_TO, LIST_NAME_TO = self.get_id_name(TEST_LIST_TO)

    def test_create_purge(self):
        c = "{} --create".format(LIST_NAME)
        assert nicotools.main(self.param(c))
        c = "{} --id --export --out {}{}_export.txt".format(LIST_ID, SAVE_DIR, LIST_NAME)
        assert nicotools.main(self.param(c))
        c = "{} --id --show".format(LIST_ID)
        assert nicotools.main(self.param(c))
        c = "{} --id --show --show --out {}{}_show.txt".format(LIST_ID, SAVE_DIR, LIST_NAME)
        assert nicotools.main(self.param(c))
        c = "{} --id --purge --yes".format(LIST_ID)
        assert nicotools.main(self.param(c))

    def test_export_everything(self):
        c = "* --export --everything"
        assert nicotools.main(self.param(c))

    def test_export_meta(self):
        c = "* --export"
        assert nicotools.main(self.param(c))

    def test_show_meta_tsv(self):
        c = "* --show"
        assert nicotools.main(self.param(c))

    def test_show_meta_table(self):
        c = "* --show --show"
        assert nicotools.main(self.param(c))

    def test_show_everything_tsv(self):
        c = "* --show --everything"
        assert nicotools.main(self.param(c))

    def test_show_everything_table(self):
        c = "* --show --show --everything"
        assert nicotools.main(self.param(c))

    def test_okatadsuke(self):
        INSTANCE.purge_mylist(LIST_NAME, True)
        INSTANCE.purge_mylist(LIST_NAME_TO, True)


class TestErrors:
    def test_initialize(self):
        global INSTANCE, LIST_ID, LIST_NAME, LIST_ID_TO, LIST_NAME_TO
        INSTANCE = nicoml.NicoMyList(AUTH_N[0], AUTH_N[1], logger=LOGGER)
        LIST_ID, LIST_NAME = self.get_id_name(TEST_LIST)
        LIST_ID_TO, LIST_NAME_TO = self.get_id_name(TEST_LIST_TO)
        c = "とりあえずマイリスト --add {}".format(VIDEO_IDS)
        nicotools.main(self.param(c))

    def get_id_name(self, name):
        result = INSTANCE.get_list_id(name)
        if result.get("error"):
            INSTANCE.create_mylist(name)
            return self.get_id_name(name)
        return result["list_id"], result["list_name"]

    def param(self, cond):
        cond = "mylist -u {_mail} -p {_pass} " + cond
        return cond.format(_mail=AUTH_N[0], _pass=AUTH_N[1]).split(" ")

    def test_add_all(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --add *"
            nicotools.main(self.param(c))

    def test_create_deflist(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --create"
            nicotools.main(self.param(c))

    def test_purge_deflist(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --purge"
            nicotools.main(self.param(c))

    def test_copy_to_same(self):
        with pytest.raises(SystemExit):
            c = "{} --copy * --to {}".format(LIST_NAME, LIST_NAME)
            nicotools.main(self.param(c))

    def test_move_without_to(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --move *"
            nicotools.main(self.param(c))

    def test_copy_without_to(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --copy *"
            nicotools.main(self.param(c))

    def test_delete_ambiguous(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --delete sm9 *"
            nicotools.main(self.param(c))

    def test_add_all_internal(self):
        with pytest.raises(utils.MylistError):
            INSTANCE.add(utils.ALL_ITEM, "sm9")
        with pytest.raises(utils.MylistError):
            INSTANCE.add(utils.Msg.ml_default_id, utils.ALL_ITEM)

    def test_delete_ambiguous_internal(self):
        with pytest.raises(utils.MylistError):
            INSTANCE.delete(utils.Msg.ml_default_id, utils.ALL_ITEM, "sm9")

    def test_copy_same_internal(self):
        with pytest.raises(utils.MylistError):
            INSTANCE.copy(1, 1, utils.ALL_ITEM)

    def test_copy_ambiguous_internal(self):
        with pytest.raises(utils.MylistError):
            INSTANCE.copy(utils.Msg.ml_default_id, 1, utils.ALL_ITEM, "sm9")

    def test_create_allid_internal(self):
        with pytest.raises(utils.MylistError):
            INSTANCE.create_mylist(utils.Msg.ml_default_id)

    def test_create_allname_internal(self):
        with pytest.raises(utils.MylistError):
            INSTANCE.create_mylist(utils.Msg.ml_default_name)

    def test_create_null_internal(self):
        with pytest.raises(utils.MylistError):
            INSTANCE.create_mylist("")

    def test_purge_def_internal(self):
        with pytest.raises(utils.MylistError):
            INSTANCE.purge_mylist(utils.Msg.ml_default_name)

    def test_purge_all_internal(self):
        with pytest.raises(utils.MylistError):
            INSTANCE.create_mylist(utils.ALL_ITEM)

    def test_purge_null_internal(self):
        with pytest.raises(utils.MylistError):
            INSTANCE.create_mylist("")

    def test_no_commands(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト"
            nicotools.main(self.param(c))

    def test_list_not_exists_and_create_special_characters_name(self):
        c = "{} --show".format(INSANE_NAME)
        with pytest.raises(utils.MylistNotFoundError):
            nicotools.main(self.param(c))
        INSTANCE.create_mylist(INSANE_NAME)
        # 作ったばかりなのでマイリストIDは、手持ちの中で最大。
        insane_id = max(INSTANCE.mylists)
        INSTANCE.purge_mylist(insane_id, confident=True)

    def test_item_not_exists(self):
        c = "とりあえずマイリスト --delete {}".format(VIDEO_IDS)
        assert nicotools.main(self.param(c))
        c = "とりあえずマイリスト --delete {}".format(VIDEO_IDS)
        assert nicotools.main(self.param(c)) is False

    def test_okatadsuke(self):
        INSTANCE.purge_mylist(LIST_NAME, True)
        INSTANCE.purge_mylist(LIST_NAME_TO, True)
