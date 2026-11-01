import random
import threading
import time
from functools import wraps

import streamlit as st
import streamlit.components.v1 as components

# 기본 정답판
BASE_GRID = [
    [1, 2, 3, 4, 5, 6, 7, 8, 9],
    [4, 5, 6, 7, 8, 9, 1, 2, 3],
    [7, 8, 9, 1, 2, 3, 4, 5, 6],
    [2, 3, 1, 8, 9, 7, 5, 6, 4],
    [5, 6, 4, 2, 3, 1, 8, 9, 7],
    [8, 9, 7, 5, 6, 4, 2, 3, 1],
    [3, 1, 2, 6, 4, 5, 9, 7, 8],
    [6, 4, 5, 9, 7, 8, 3, 1, 2],
    [9, 7, 8, 3, 1, 2, 6, 4, 5],
]
DIGITS = set("123456789")
MAX_RANK = 10


# secrets.toml 값 읽기
def read_secret(key, default=None, section=None):
    try:
        if section:
            return st.secrets[section][key]
        return st.secrets[key]
    except Exception:
        return default


GAME_TITLE = read_secret("title", "🧩 스도쿠 게임", section="game")
ADMIN_PASSWORD = read_secret("ADMIN_PASSWORD")


# 호출 횟수 세는 데코레이터
def count_calls(counter_name):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            st.session_state[counter_name] = st.session_state.get(counter_name, 0) + 1
            return func(*args, **kwargs)
        return wrapper
    return decorator


# 문제 생성 (같은 seed면 캐시 사용)
@st.cache_data
def make_puzzle(seed, hint_ratio):
    rng = random.Random(seed)
    mapping = list(range(1, 10))
    rng.shuffle(mapping)
    solution = [[str(mapping[BASE_GRID[i][j] - 1]) for j in range(9)] for i in range(9)]
    puzzle = [[solution[i][j] if rng.random() <= hint_ratio else "" for j in range(9)]
              for i in range(9)]
    return puzzle, solution


# 모든 사용자가 같이 쓰는 등수표
@st.cache_resource
def get_ranking_board():
    return {"records": [], "lock": threading.Lock()}


def add_record(name, seconds, hint_ratio):
    board = get_ranking_board()
    with board["lock"]:
        board["records"].append({"name": name, "seconds": seconds, "hint": hint_ratio})
        board["records"].sort(key=lambda r: r["seconds"])


def reset_ranking():
    board = get_ranking_board()
    with board["lock"]:
        board["records"].clear()


def fmt_time(seconds):
    seconds = int(seconds)
    return "%02d:%02d" % (seconds // 60, seconds % 60)


# 행, 열, 3x3 검사
@count_calls("check_count")
def check_board(board):
    for i in range(9):
        for j in range(9):
            if board[i][j] == "":
                return "empty", "완료를 다 하시고 버튼을 눌러주세요"
            if board[i][j] not in DIGITS:
                return "wrong", "%d행 %d열에 1~9가 아닌 값이 있습니다" % (i + 1, j + 1)
    for i in range(9):
        if set(board[i]) != DIGITS:
            return "wrong", "틀렸습니다, 다시 시도해주세요 (%d행)" % (i + 1)
    for j in range(9):
        if set(board[i][j] for i in range(9)) != DIGITS:
            return "wrong", "틀렸습니다, 다시 시도해주세요 (%d열)" % (j + 1)
    for bi in (0, 3, 6):
        for bj in (0, 3, 6):
            box = {board[bi + a][bj + b] for a in range(3) for b in range(3)}
            if box != DIGITS:
                return "wrong", "틀렸습니다, 다시 시도해주세요 (%d번째 3x3 칸)" % ((bi // 3) * 3 + bj // 3 + 1)
    return "ok", "!!! ~~~Congratulation~~~ !!!"


# 새 게임 시작 (session_state에 상태 저장)
def new_game():
    hint_ratio = st.session_state.get("hint_ratio", 0.5)
    st.session_state.seed = random.randint(0, 10**9)
    st.session_state.game_id = st.session_state.get("game_id", 0) + 1
    st.session_state.puzzle, st.session_state.solution = make_puzzle(st.session_state.seed, hint_ratio)
    st.session_state.start_time = time.time()
    st.session_state.finished = False
    st.session_state.final_time = None
    st.session_state.recorded = False
    st.session_state.result = None
    st.session_state.check_count = 0


def current_board():
    gid = st.session_state.game_id
    puzzle = st.session_state.puzzle
    return [[puzzle[i][j] if puzzle[i][j] else
             st.session_state.get("cell_%d_%d_%d" % (gid, i, j), "").strip()
             for j in range(9)] for i in range(9)]


st.set_page_config(page_title="Sudoku", page_icon="🧩", layout="wide")

st.markdown("""
<style>
div[data-testid="stTextInput"] input {
    text-align: center; font-size: 1.5rem; font-weight: 600;
    height: 3rem; padding: 0; color: #d62728;
}
div[data-testid="stTextInput"] input:disabled {
    color: #111 !important; -webkit-text-fill-color: #111;
    background-color: #e9eef5; opacity: 1;
}
div[data-testid="stTextInput"] { margin-bottom: -0.6rem; }
.st-key-board [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.3rem !important; }
.st-key-board [data-testid="stColumn"] { min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }
.st-key-board [data-testid="stColumn"]:nth-child(3),
.st-key-board [data-testid="stColumn"]:nth-child(6) { margin-right: 0.7rem; }
</style>
""", unsafe_allow_html=True)

if "game_id" not in st.session_state:
    new_game()

st.title(GAME_TITLE)

left, right = st.columns([3, 2], gap="large")

# 관리자 메뉴 (이 부분만 따로 다시 그려짐)
@st.fragment
def admin_panel():
    st.subheader("🔒 관리자")
    if ADMIN_PASSWORD is None:
        st.caption("secrets.toml 에 ADMIN_PASSWORD 가 없어 관리자 기능이 꺼져 있습니다.")
    else:
        pw = st.text_input("관리자 비밀번호", type="password")
        if pw:
            if pw == ADMIN_PASSWORD:
                st.success("관리자 인증 완료")
                if st.button("등수표 초기화", use_container_width=True):
                    reset_ranking()
                    st.rerun(scope="app")
                if st.checkbox("정답 보기"):
                    st.code("\n".join(" ".join(r) for r in st.session_state.solution))
            else:
                st.error("비밀번호가 틀렸습니다")


# 타이머 (브라우저에서 1초마다 갱신)
def timer_box():
    st.caption("⏱ 소요시간")
    if st.session_state.finished:
        elapsed, running = st.session_state.final_time, "false"
    else:
        elapsed, running = time.time() - st.session_state.start_time, "true"
    components.html('''
<div id="t" style="font-family:'Source Sans Pro',sans-serif;font-size:2.2rem;color:#31333F;">00:00</div>
<script>
const base = Date.now() - %d;
const running = %s;
function draw() {
  const e = Math.floor((Date.now() - base) / 1000);
  document.getElementById("t").textContent =
    String(Math.floor(e / 60)).padStart(2, "0") + ":" + String(e %% 60).padStart(2, "0");
}
draw();
if (running) setInterval(draw, 1000);
</script>''' % (int(elapsed * 1000), running), height=55)


# 사이드바
with st.sidebar:
    st.header("게임 설정")
    st.slider("힌트 비율 (클수록 쉬움)", 0.3, 0.9, 0.5, 0.05, key="hint_ratio")
    if st.button("🔀 섞기 (새 게임)", use_container_width=True):
        new_game()
        st.rerun()

    st.divider()
    admin_panel()



# 스도쿠 판
with left, st.container(key="board"):
    gid = st.session_state.game_id
    puzzle = st.session_state.puzzle
    for i in range(9):
        if i in (3, 6):
            st.write("")
        cols = st.columns(9)
        for j in range(9):
            with cols[j]:
                if puzzle[i][j]:
                    st.text_input("r%dc%d" % (i, j), value=puzzle[i][j], disabled=True,
                                  key="hint_%d_%d_%d" % (gid, i, j), label_visibility="collapsed")
                else:
                    st.text_input("r%dc%d" % (i, j), max_chars=1, placeholder="",
                                  key="cell_%d_%d_%d" % (gid, i, j), label_visibility="collapsed",
                                  disabled=st.session_state.finished)

# 오른쪽 패널
with right:
    timer_box()
    filled = sum(1 for row in current_board() for v in row if v)
    st.progress(filled / 81, text="채운 칸 %d / 81" % filled)

    if st.button("✅ 완료 검사", type="primary", use_container_width=True,
                 disabled=st.session_state.finished):
        status, msg = check_board(current_board())
        st.session_state.result = (status, msg)
        if status == "ok":
            st.session_state.finished = True
            st.session_state.final_time = round(time.time() - st.session_state.start_time, 1)
        st.rerun()

    if st.session_state.result:
        status, msg = st.session_state.result
        (st.success if status == "ok" else st.warning if status == "empty" else st.error)(msg)
    st.caption("완료 검사 횟수: %d회" % st.session_state.get("check_count", 0))

    # 정답이면 이름 입력 후 등수 기록
    if st.session_state.finished and not st.session_state.recorded:
        st.balloons()
        with st.form("rank_form"):
            name = st.text_input("이름을 입력하세요", max_chars=20)
            if st.form_submit_button("등수표에 기록"):
                add_record(name.strip() or "익명", st.session_state.final_time,
                           st.session_state.hint_ratio)
                st.session_state.recorded = True
                st.rerun()

    st.subheader("🏆 등수표 (모든 사용자 공유)")
    records = get_ranking_board()["records"][:MAX_RANK]
    if records:
        st.dataframe(
            [{"순위": "%d위" % (k + 1), "이름": r["name"], "소요시간": fmt_time(r["seconds"]),
              "힌트 비율": r["hint"]} for k, r in enumerate(records)],
            hide_index=True, use_container_width=True)
    else:
        st.caption("아직 기록이 없습니다. 첫 번째 주인공이 되어 보세요!")
