"""
Single-file Car Maze game with:
- 3 FIXED mazes
- Leaderboard (persistent in scores.json)
- Race rooms (non-real-time 2-player)
- Ad placeholder in center
- All game & DAA logic in Python (Flask)
Usage:
    pip install flask
    python app.py
Open: http://127.0.0.1:5000/
"""
from flask import Flask, request, jsonify, render_template_string
from collections import deque
import random, json, os, time, uuid, threading

app = Flask(__name__)
LOCK = threading.Lock()

# -------------------------
# Fixed mazes (3 choices)
# -------------------------
# 0 = path, 1 = wall, 2 = oil, 3 = exit
MAZES = []

MAZES.append({
    "name": "Forest Small",
    "grid": [
        [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
        [1,0,2,0,1,0,0,0,1,0,0,0,2,0,1],
        [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1],
        [1,0,0,0,2,0,1,0,0,0,1,0,1,0,1],
        [1,1,1,0,1,0,1,0,1,0,1,0,0,0,1],
        [1,0,0,0,1,0,0,0,1,0,1,0,1,0,1],
        [1,2,1,0,1,0,1,0,2,0,1,0,1,0,1],
        [1,0,1,0,1,0,1,0,1,0,1,0,1,3,1],
        [1,0,0,0,0,0,1,0,1,0,0,0,1,0,1],
        [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1],
        [1,0,1,0,0,0,0,0,1,0,1,0,0,0,1],
        [1,0,1,0,1,1,1,0,1,0,1,1,1,0,1],
        [1,0,0,0,1,0,2,0,0,0,0,0,1,0,1],
        [1,2,1,0,1,0,1,0,1,1,1,0,1,0,1],
        [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
    ]
})

MAZES.append({
    "name": "Dense Grove",
    "grid": [
        [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
        [1,0,0,0,1,0,1,0,1,0,2,0,0,2,1],
        [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1],
        [1,0,1,0,0,0,1,0,0,0,1,0,0,0,1],
        [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1],
        [1,0,0,0,1,0,0,0,1,0,0,0,1,0,1],
        [1,0,1,0,1,0,1,0,2,0,1,0,1,0,1],
        [1,0,1,0,1,0,1,0,1,0,1,0,1,3,1],
        [1,2,0,0,0,0,1,0,1,0,0,0,1,0,1],
        [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1],
        [1,0,1,0,0,0,0,0,1,0,1,0,0,0,1],
        [1,0,1,0,1,1,1,0,1,0,1,1,1,0,1],
        [1,0,0,2,1,0,2,0,0,0,0,0,1,0,1],
        [1,2,1,0,1,0,1,0,1,1,1,0,1,0,1],
        [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
    ]
})

MAZES.append({
    "name": "Old Track",
    "grid": [
        [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
        [1,2,0,0,1,0,0,0,1,0,0,0,2,0,1],
        [1,0,1,0,1,1,1,0,1,0,1,0,1,0,1],
        [1,0,1,0,0,0,1,0,0,0,1,0,1,0,1],
        [1,0,1,0,1,0,1,0,1,0,1,0,0,0,1],
        [1,0,1,0,1,0,0,0,1,0,1,0,1,0,1],
        [1,2,1,0,1,0,1,0,2,0,1,0,1,0,1],
        [1,0,1,0,1,0,1,0,1,0,1,0,1,3,1],
        [1,0,0,0,0,0,1,0,1,0,0,0,1,0,1],
        [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1],
        [1,0,1,0,0,0,0,0,1,0,1,0,0,0,1],
        [1,0,1,0,1,1,1,0,1,0,1,1,1,0,1],
        [1,0,0,0,1,0,2,0,0,0,0,0,1,0,1],
        [1,2,1,0,1,0,1,0,1,1,1,0,1,0,1],
        [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
    ]
})

# -------------------------
# Sessions & Rooms storage
# -------------------------
SESSIONS = {}   # session_id -> game state dict
ROOMS = {}      # room_id -> {maze_index, sessions: [session_ids], results: {session_id: time}}

SCORES_FILE = "scores.json"
# ensure scores.json exists
if not os.path.exists(SCORES_FILE):
    with open(SCORES_FILE,"w") as f:
        json.dump([], f)

def load_scores():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT player, maze, score, time FROM leaderboard ORDER BY score DESC, time ASC LIMIT 100")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def save_score(entry):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO leaderboard (player, maze, score, time) VALUES (%s, %s, %s, %s)",
        (entry["player"], entry["maze"], entry["score"], entry["time"])
    )
    conn.commit()
    cur.close()
    conn.close()


# -------------------------
# Game utilities (per-session)
# -------------------------
def new_session(maze_index, player_name):
    maze_template = MAZES[maze_index]["grid"]
    # deep copy
    maze = [row[:] for row in maze_template]
    # find start (first empty tile near top-left)
    start = None
    for r in range(len(maze)):
        for c in range(len(maze[0])):
            if maze[r][c] == 0:
                start = (r,c)
                break
        if start: break
    # find exit coordinates
    exit_pos = None
    for r in range(len(maze)):
        for c in range(len(maze[0])):
            if maze[r][c] == 3:
                exit_pos = (r,c)
                break
        if exit_pos: break

    # random-ish enemy placements (but not on start)
    enemies = []
    free = [(r,c) for r in range(len(maze)) for c in range(len(maze[0])) if maze[r][c] == 0 and (r,c) != start]
    random.shuffle(free)
    for i in range(3):
        if i < len(free):
            enemies.append(list(free[i]))

    sid = str(uuid.uuid4())
    SESSIONS[sid] = {
        "maze_index": maze_index,
        "maze": maze,
        "player_name": player_name or "Player",
        "player": list(start),
        "enemies": enemies,
        "start_time": time.time(),
        "finished": False,
        "finish_time": None,
        "score": 0
    }
    return sid

def bfs_shortest(maze, start, goal):
    R = len(maze); C = len(maze[0])
    sr, sc = start; gr, gc = goal
    if not (0 <= gr < R and 0 <= gc < C): return []
    if maze[gr][gc] == 1: return []
    q = deque()
    q.append((sr,sc))
    prev = { (sr,sc): None }
    moves = [(1,0),(-1,0),(0,1),(0,-1)]
    while q:
        r,c = q.popleft()
        if (r,c) == (gr,gc):
            break
        for dr,dc in moves:
            nr, nc = r+dr, c+dc
            if 0 <= nr < R and 0 <= nc < C and maze[nr][nc] != 1 and (nr,nc) not in prev:
                prev[(nr,nc)] = (r,c)
                q.append((nr,nc))
    if (gr,gc) not in prev:
        return []
    # reconstruct
    path = []
    cur = (gr,gc)
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path

# -------------------------
# Session actions
# -------------------------
def step_session_move(sid, direction):
    s = SESSIONS.get(sid)
    if not s:
        return {"error":"Invalid session id"}, 400
    maze = s["maze"]
    pr, pc = s["player"]
    dr = dc = 0
    if direction == "up": dr = -1
    elif direction == "down": dr = 1
    elif direction == "left": dc = -1
    elif direction == "right": dc = 1
    nr, nc = pr + dr, pc + dc
    R = len(maze); C = len(maze[0])
    if not (0 <= nr < R and 0 <= nc < C):
        return {"ok":True, "state":s}
    if maze[nr][nc] != 1:
        s["player"] = [nr, nc]
        if maze[nr][nc] == 2:
            maze[nr][nc] = 0
            s["score"] += 25
        # check exit
        if maze[nr][nc] == 3:
            s["finished"] = True
            s["finish_time"] = time.time()
            # record score
            elapsed = s["finish_time"] - s["start_time"]
            s["score"] += 200
            save_score({"player": s["player_name"], "maze": MAZES[s["maze_index"]]["name"], "time": elapsed, "score": s["score"], "when": time.time()})
            return {"ok":True, "state":s, "status":"win", "elapsed": elapsed}
    # move enemies toward player (BFS one step)
    exit_coord = None
    for r_ in range(len(maze)):
        for c_ in range(len(maze[0])):
            if maze[r_][c_] == 3:
                exit_coord = (r_, c_)
                break
        if exit_coord: break
    # enemies move
    for i, e in enumerate(s["enemies"]):
        path = bfs_shortest(maze, tuple(e), tuple(s["player"]))
        if len(path) >= 2:
            s["enemies"][i] = list(path[1])
        # collision
        if s["enemies"][i][0] == s["player"][0] and s["enemies"][i][1] == s["player"][1]:
            # player caught: reset to start (but keep score penalty)
            s["score"] = max(0, s["score"] - 50)
            # respawn player at initial start (first tile with 0)
            start = None
            for rr in range(len(maze)):
                for cc in range(len(maze[0])):
                    if maze[rr][cc] == 0:
                        start = (rr,cc); break
                if start: break
            s["player"] = list(start)
            return {"ok":True, "state":s, "status":"caught"}
    return {"ok":True, "state":s}

# -------------------------
# Flask routes
# -------------------------
@app.route("/")
def index():
    # render the single-page app (HTML+JS inline)
    return render_template_string(INDEX_HTML, mazes=[{"idx":i,"name":m["name"]} for i,m in enumerate(MAZES)])

@app.route("/create_session", methods=["POST"])
def create_session():
    data = request.json or {}
    maze_index = int(data.get("maze_index", 0))
    player_name = data.get("player_name","Player")
    mode = data.get("mode","single")  # "single" or "race"
    room = data.get("room")  # optional join room
    sid = new_session(maze_index, player_name)
    # attach session to room if race mode
    if mode == "race":
        if room:
            # join existing room
            room_obj = ROOMS.get(room)
            if room_obj and room_obj["maze_index"] == maze_index:
                room_obj["sessions"].append(sid)
            else:
                return jsonify({"error":"Invalid room or maze mismatch"}), 400
        else:
            # create room
            rid = str(uuid.uuid4())[:8]
            ROOMS[rid] = {"maze_index": maze_index, "sessions":[sid], "results":{}}
            room = rid
    return jsonify({"session_id": sid, "room": room})

@app.route("/create_room", methods=["POST"])
def create_room():
    data = request.json or {}
    maze_index = int(data.get("maze_index", 0))
    rid = str(uuid.uuid4())[:8]
    ROOMS[rid] = {"maze_index":maze_index, "sessions":[], "results":{}}
    return jsonify({"room":rid})

@app.route("/join_room", methods=["POST"])
def join_room():
    data = request.json or {}
    rid = data.get("room")
    maze_index = int(data.get("maze_index", 0))
    if rid not in ROOMS:
        return jsonify({"error":"No such room"}), 400
    room_obj = ROOMS[rid]
    if room_obj["maze_index"] != maze_index:
        return jsonify({"error":"Maze mismatch"}), 400
    # create session and add
    sid = new_session(maze_index, data.get("player_name","Player"))
    room_obj["sessions"].append(sid)
    return jsonify({"session_id": sid})

@app.route("/move", methods=["POST"])
def move_endpoint():
    data = request.json or {}
    sid = data.get("session_id")
    direction = data.get("dir", "none")
    if not sid or sid not in SESSIONS:
        return jsonify({"error":"session missing"}), 400
    res = step_session_move(sid, direction)
    return jsonify(res)

@app.route("/state/<session_id>")
def state(session_id):
    s = SESSIONS.get(session_id)
    if not s:
        return jsonify({"error":"invalid"}), 400
    # give public state
    return jsonify({
        "maze": s["maze"],
        "player": s["player"],
        "enemies": s["enemies"],
        "player_name": s["player_name"],
        "score": s["score"],
        "finished": s["finished"]
    })

@app.route("/leaderboard")
def leaderboard():
    scores = load_scores()
    # sort by score desc then time ascending
    scores_sorted = sorted(scores, key=lambda x:(-x["score"], x.get("time",999999)))
    return jsonify(scores_sorted[:100])

@app.route("/submit_race", methods=["POST"])
def submit_race():
    data = request.json or {}
    rid = data.get("room")
    sid = data.get("session_id")
    if rid not in ROOMS:
        return jsonify({"error":"no room"}), 400
    if sid not in SESSIONS:
        return jsonify({"error":"no session"}), 400
    s = SESSIONS[sid]
    if not s["finished"]:
        return jsonify({"error":"not finished"}), 400
    elapsed = s["finish_time"] - s["start_time"]
    ROOMS[rid]["results"][sid] = {"player": s["player_name"], "time": elapsed, "score": s["score"]}
    # if both players submitted (we allow up to 2 sessions), compute results
    if len(ROOMS[rid]["sessions"]) >= 2 and len(ROOMS[rid]["results"]) >= 2:
        # prepare summary
        res = sorted(ROOMS[rid]["results"].items(), key=lambda kv: kv[1]["time"])
        return jsonify({"status":"complete","results":[v for k,v in res]})
    return jsonify({"status":"waiting"})

# -------------------------
# Minimal HTML + JS client
# -------------------------
INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Car Maze — Multi Maze + Leaderboard + Race</title>
  <style>
    body{font-family:Arial;background:#062a17;color:#e8f8ec;margin:10px}
    .container{display:flex;gap:12px;align-items:flex-start}
    #left{width:760px}
    canvas{background:#203020;border-radius:8px;box-shadow:0 8px 30px rgba(0,0,0,0.6)}
    #controls{width:360px;background:linear-gradient(#083724,#05241b);padding:12px;border-radius:8px}
    .row{margin:8px 0}
    button{padding:8px;border-radius:6px;border:none;background:#2ea04b;color:white;cursor:pointer}
    input,select{padding:6px;border-radius:6px;border:1px solid #234}
    #adbox{width:300px;height:150px;background:#fff1a8;color:#333;margin:auto;display:flex;align-items:center;justify-content:center;border-radius:8px}
    #chat{font-size:13px;color:#bfe3c8;margin-top:8px}
  </style>
</head>
<body>
  <h1>🚗 Car Maze — Choose Maze, Play, Leaderboard & Race</h1>
  <div class="container">
    <div id="left">
      <div id="adbox">AD PLACEHOLDER</div>
      <canvas id="board" width="750" height="750"></canvas>
    </div>
    <div id="controls">
      <div class="row">
        <label>Your name: <input id="playerName" value="Player"></label>
      </div>
      <div class="row">
        <label>Choose maze:
          <select id="mazeSelect">
            {% for m in mazes %}
            <option value="{{m.idx}}">{{m.name}}</option>
            {% endfor %}
          </select>
        </label>
      </div>

      <div class="row">
        <button id="newGame">Start Local Game</button>
      </div>

      <hr style="border-color:#233">

      <div class="row"><strong>Leaderboard</strong></div>
      <div class="row"><button id="viewLB">View Leaderboard</button></div>
      <div id="lb" style="max-height:220px;overflow:auto"></div>

      <hr style="border-color:#233">

      <div class="row"><strong>Race Mode (non real-time)</strong></div>
      <div class="row">
        <button id="createRoom">Create Room</button>
        <input id="roomId" placeholder="Room ID" style="width:140px">
        <button id="joinRoom">Join Room</button>
      </div>
      <div id="raceInfo" class="row"></div>

      <div id="chat"></div>
    </div>
  </div>

<script>
const canvas = document.getElementById("board");
const ctx = canvas.getContext("2d");
const TILE = 50;
let sessionId = null;
let currentState = null;

// draw function
function drawState(state){
  if(!state) return;
  const maze = state.maze;
  ctx.clearRect(0,0,canvas.width,canvas.height);
  for(let r=0;r<maze.length;r++){
    for(let c=0;c<maze[0].length;c++){
      const v = maze[r][c];
      const x = c * TILE, y = r * TILE;
      if(v === 1){ ctx.fillStyle="#102010"; ctx.fillRect(x,y,TILE,TILE); ctx.fillStyle="#0a7a3f"; ctx.beginPath(); ctx.ellipse(x+TILE*0.5, y+TILE*0.35, TILE*0.28, TILE*0.18, 0,0,Math.PI*2); ctx.fill(); }
      else { ctx.fillStyle="#2e8b57"; ctx.fillRect(x,y,TILE,TILE); }
      if(v === 2){ ctx.fillStyle="#ffd54f"; ctx.beginPath(); ctx.arc(x+TILE*0.5,y+TILE*0.5,12,0,Math.PI*2); ctx.fill(); }
      if(v === 3){ ctx.fillStyle="#553388"; ctx.fillRect(x,y,TILE,TILE); ctx.fillStyle="#ffd27a"; ctx.font="14px monospace"; ctx.textAlign="center"; ctx.fillText('┌───┐', x+TILE/2, y+TILE/2 - 8); ctx.fillText('│   │', x+TILE/2, y+TILE/2 + 6); ctx.fillText('└───┘', x+TILE/2, y+TILE/2 + 20); }
    }
  }
  // player
  const p = state.player;
  ctx.fillStyle="#00ffff"; ctx.fillRect(p[1]*TILE+10,p[0]*TILE+10,30,30);
  // enemies
  state.enemies.forEach(e=>{
    ctx.fillStyle="#ffffff"; ctx.beginPath(); ctx.arc(e[1]*TILE+25, e[0]*TILE+25, 14,0,Math.PI*2); ctx.fill();
    ctx.fillStyle="#000"; ctx.beginPath(); ctx.arc(e[1]*TILE+21, e[0]*TILE+22, 3,0,Math.PI*2); ctx.fill();
  });
  // stats
  document.getElementById('chat').innerText = "Name: "+ (state.player_name || "") + "   Score: " + (state.score || 0);
}

// utilities to fetch
async function api(path, opts){
  const res = await fetch(path, opts);
  return res.json();
}

// start new local session
document.getElementById('newGame').addEventListener('click', async ()=>{
  const player = document.getElementById('playerName').value || 'Player';
  const maze_index = parseInt(document.getElementById('mazeSelect').value);
  const resp = await api('/create_session', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({maze_index, player_name: player, mode: 'single'})
  });
  sessionId = resp.session_id;
  refresh();
});

// refresh state
async function refresh(){
  if(!sessionId) return;
  const res = await api('/state/'+sessionId);
  if(res.error){ console.error(res); return; }
  currentState = res;
  drawState(res);
}

// handle keyboard
window.addEventListener('keydown', async (e)=>{
  if(!sessionId) return;
  const map = {ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right'};
  const dir = map[e.key];
  if(!dir) return;
  const res = await api('/move',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({session_id: sessionId, dir})
  });
  if(res.status === 'win'){
    alert('You won! Time: '+ (res.elapsed ? res.elapsed.toFixed(2) : 'N/A') + 's. Score saved to leaderboard.');
  } else if(res.status === 'caught'){
    alert('You were caught! Lost some points and respawned.');
  }
  // update local view
  await refresh();
});

// leaderboard view
document.getElementById('viewLB').addEventListener('click', async ()=>{
  const sc = await api('/leaderboard');
  let html = '<ol>';
  sc.forEach(s => { html += `<li>${s.player} — ${s.maze} — score:${s.score} time:${s.time ? s.time.toFixed(2):'N/A'}</li>`; });
  html += '</ol>';
  document.getElementById('lb').innerHTML = html;
});

// create room
document.getElementById('createRoom').addEventListener('click', async ()=>{
  const maze_index = parseInt(document.getElementById('mazeSelect').value);
  const resp = await api('/create_room',{method:'POST',headers:{'Content-Type':'application/json'}, body: JSON.stringify({maze_index})});
  const rid = resp.room;
  document.getElementById('raceInfo').innerText = 'Room created: ' + rid + '. Share this ID with opponent. Now click Join Room with same ID to join.';
  // automatically create session and join
  const player = document.getElementById('playerName').value || 'Player';
  const cr = await api('/create_session',{method:'POST',headers:{'Content-Type':'application/json'}, body: JSON.stringify({maze_index, player_name:player, mode:'race', room:rid})});
  sessionId = cr.session_id;
  document.getElementById('roomId').value = rid;
  refresh();
});

// join room
document.getElementById('joinRoom').addEventListener('click', async ()=>{
  const rid = document.getElementById('roomId').value.trim();
  const maze_index = parseInt(document.getElementById('mazeSelect').value);
  if(!rid){ alert('Enter room id'); return; }
  // create new session and add to room
  const player = document.getElementById('playerName').value || 'Player';
  const resp = await api('/join_room',{method:'POST',headers:{'Content-Type':'application/json'}, body: JSON.stringify({room:rid, maze_index, player_name:player})});
  if(resp.error){ alert(resp.error); return; }
  sessionId = resp.session_id;
  document.getElementById('raceInfo').innerText = 'Joined room: ' + rid + '. Play and when you finish, click Submit Race (auto submit on win).';
  refresh();
});

// submit race (automatic when finishing stored in server; client can poll for room results)
async function pollRoom(rid){
  // naive: ask server leaderboard for matching results in ROOMS (no direct endpoint) -> rely on submit_race replies
}

// initial: select default maze, no session
</script>
</body>
</html>
"""

# -------------------------
# Run server
# -------------------------
if __name__ == "__main__":
    print("Run: http://127.0.0.1:5000/")
    app.run(debug=True)


import mysql.connector

def get_db():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Yuiop@09876",
        database="carmaze29"
    )
    return conn
