import streamlit as st
import requests
import base64
import sqlite3
from datetime import date
from googleapiclient.discovery import build
import pandas as pd
import plotly.express as px


st.set_page_config(
    page_title="Musify Insights",
    page_icon="🎵",
    layout="wide"
)

# -----------------------------------------------------------
# CSS POUR LA PERSONNALISATION
st.markdown(
    """
    <style>
    /* Global Font */
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif;
        background-color: #121212;
        color: white;
        height: 100%;
        margin: 0;
        display: flex;
        justify-content: center;
        align-items: center;
        flex-direction: column;
    }

    /* Header */
    .css-10trblm {
        background: linear-gradient(90deg, #1db954, #191414);
        color: white;
        padding: 40px 0;
        text-align: center;
        width: 100%;
        margin: 0;
        flex: 0 1 auto;
    }

    /* Logo and Text Container */
    .header-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        margin-bottom: 20px;
    }

    .logo img {
        width: 200px;
        display: block;
    }

    .header-text {
        text-align: center;
        color: white;
        margin-top: 20px;
    }

    .header-text h1 {
        font-size: 36px;
        margin-bottom: 10px;
    }

    .header-text p {
        font-size: 18px;
        color: #1db954;
    }

    /* Buttons */
    .stButton>button {
        color: white;
        background: #1db954;
        border-radius: 8px;
        padding: 12px 24px;
        font-size: 16px;
        width: 100%;
        transition: background 0.3s ease;
    }
    .stButton>button:hover {
        background: #1ed760;
    }

    /* Main content */
    .main-container {
        padding: 20px;
        background-color: #191414;
        color: white;
        border-radius: 12px;
        margin-top: 20px;
        margin-bottom: 30px;
    }

    /* DataFrames */
    .dataframe {
        border: 1px solid #1db954;
        border-radius: 8px;
        padding: 10px;
        margin-top: 20px;
    }

    /* Tabs */
    .stTabs [role="tablist"] {
        border-bottom: 2px solid #1db954;
        display: flex;
        justify-content: center;
        margin-top: 30px;
    }

    .stTabs button {
        background-color: #121212;
        color: white;
        font-size: 16px;
        padding: 10px 20px;
        border-radius: 10px;
        transition: background 0.3s ease;
    }

    .stTabs button:hover {
        background-color: #1db954;
    }

    /* Footer styles */
    .footer {
        text-align: center;
        font-size: 14px;
        color: gray;
        padding-top: 30px;
    }

    /* Spacing in containers */
    .container {
        margin-top: 20px;
        padding-left: 20px;
        padding-right: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# Configuration de la page
# -----------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------
# >>> SPOTIFY
SPOTIFY_CLIENT_ID = "2a4cf4aebe7946a0ab1782a95c6a72ae"
SPOTIFY_CLIENT_SECRET = "165c9df45fef4cba90962018ad7337f9"

# >>> YOUTUBE
YOUTUBE_API_KEY = "AIzaSyD6l1-PtViIAEQT-J21vaQBXzaCaMnd6ho"

DB_NAME = "manager_dashboard.db"

# -----------------------------------------------------------
# FONCTIONS SPOTIFY
# -----------------------------------------------------------
def get_spotify_access_token():
    url = "https://accounts.spotify.com/api/token"
    auth_string = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials"
    }
    r = requests.post(url, headers=headers, data=data)
    if r.status_code == 200:
        return r.json()["access_token"]
    else:
        st.error(f"Erreur token Spotify: {r.status_code} - {r.text}")
        return None

def search_spotify_artist(token, artist_name):
    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "q": artist_name,
        "type": "artist",
        "limit": 1
    }
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 200:
        items = r.json().get("artists", {}).get("items", [])
        if items:
            return items[0]["id"]
    return None

def get_artist_info_spotify(token, artist_id):
    url = f"https://api.spotify.com/v1/artists/{artist_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    else:
        return None

def get_artist_top_tracks(token, artist_id, market="FR"):
    url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"market": market}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 200:
        return r.json().get("tracks", [])
    return []

# -----------------------------------------------------------
# FONCTIONS YOUTUBE
# -----------------------------------------------------------
def get_youtube_service():
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

def search_youtube_channels_for_track(youtube, artist_name, track_name, max_results=3):
    """
    Recherche 'artist_name + track_name' dans YouTube, filtre sur type="video",
    renvoie les channelId (3 vidéos max).
    """
    query = f"{artist_name} {track_name}"
    req = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=max_results
    )
    resp = req.execute()
    items = resp.get("items", [])
    channel_ids = []
    for it in items:
        snippet = it["snippet"]
        cid = snippet["channelId"]
        channel_ids.append(cid)
    return channel_ids

def get_channel_stats(youtube, channel_ids):
    """
    Retourne un dict {channelId: {"title":..., "subs":...}}
    pour la liste de channel_ids fournie.
    """
    stats = {}
    if not channel_ids:
        return stats
    req = youtube.channels().list(
        part="statistics,snippet",
        id=",".join(channel_ids)
    )
    resp = req.execute()
    for c in resp.get("items", []):
        cid = c["id"]
        title = c["snippet"].get("title", "Unknown")
        subs_str = c["statistics"].get("subscriberCount", "0")
        subs = int(subs_str)
        stats[cid] = {
            "title": title,
            "subs": subs
        }
    return stats

def get_channel_statistics(youtube, channel_id):
    """Petit util pour récupérer 1 channel_id seulement."""
    d = get_channel_stats(youtube, [channel_id])
    return d.get(channel_id)

def get_uploads_playlist_id(youtube, channel_id):
    req = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    )
    resp = req.execute()
    items = resp.get("items", [])
    if not items:
        return None
    uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    return uploads_id

def list_all_videos_in_playlist(youtube, playlist_id):
    videos = []
    page_token = None
    while True:
        req = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=page_token
        )
        resp = req.execute()
        for it in resp.get("items", []):
            snippet = it["snippet"]
            vid_id = snippet["resourceId"]["videoId"]
            vid_title = snippet["title"]
            published_at = snippet["publishedAt"]
            videos.append({
                "video_id": vid_id,
                "title": vid_title,
                "published_at": published_at
            })
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return videos

def get_videos_stats(youtube, video_ids):
    stats = {}
    batch_size = 50
    for start in range(0, len(video_ids), batch_size):
        subset = video_ids[start:start+batch_size]
        req = youtube.videos().list(
            part="statistics",
            id=",".join(subset)
        )
        resp = req.execute()
        for item in resp.get("items", []):
            vid = item["id"]
            s = item["statistics"]
            stats[vid] = {
                "viewCount": int(s.get("viewCount", 0)),
                "likeCount": int(s.get("likeCount", 0)),
                "commentCount": int(s.get("commentCount", 0))
            }
    return stats

# -----------------------------------------------------------
# DB INIT
# -----------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Table artiste
    cur.execute("""
    CREATE TABLE IF NOT EXISTS artist_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_scraped TEXT NOT NULL,
        spotify_artist_id TEXT NOT NULL,
        artist_name TEXT NOT NULL,
        spotify_popularity INTEGER,
        spotify_followers INTEGER,
        youtube_channel_id TEXT,
        youtube_subs INTEGER
    )
    """)

    # Table tracks Spotify
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tracks_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_scraped TEXT NOT NULL,
        spotify_artist_id TEXT NOT NULL,
        track_name TEXT NOT NULL,
        popularity INTEGER
    )
    """)

    # Table videos YouTube
    cur.execute("""
    CREATE TABLE IF NOT EXISTS youtube_videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_scraped TEXT NOT NULL,
        youtube_channel_id TEXT NOT NULL,
        video_id TEXT NOT NULL,
        video_title TEXT NOT NULL,
        view_count INTEGER,
        like_count INTEGER,
        comment_count INTEGER
    )
    """)

    conn.commit()
    conn.close()

# -----------------------------------------------------------
# VÉRIFS ANTI-DOUBLONS
# -----------------------------------------------------------
def already_has_spotify_data_today(artist_id):
    today_str = date.today().isoformat()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM artist_stats
        WHERE date_scraped = ? AND spotify_artist_id = ?
    """, (today_str, artist_id))
    c = cur.fetchone()[0]
    conn.close()
    return (c > 0)

def already_has_youtube_data_today(channel_id):
    today_str = date.today().isoformat()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM youtube_videos
        WHERE date_scraped = ? AND youtube_channel_id = ?
    """, (today_str, channel_id))
    c = cur.fetchone()[0]
    conn.close()
    return (c > 0)

# -----------------------------------------------------------
# INSERTION
# -----------------------------------------------------------
def insert_spotify_data(artist_id, artist_name, popularity, followers):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    d = date.today().isoformat()
    cur.execute("""
    INSERT INTO artist_stats(date_scraped, spotify_artist_id, artist_name,
                             spotify_popularity, spotify_followers,
                             youtube_channel_id, youtube_subs)
    VALUES (?, ?, ?, ?, ?, NULL, NULL)
    """, (d, artist_id, artist_name, popularity, followers))
    conn.commit()
    conn.close()

def insert_spotify_tracks(artist_id, top_tracks):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    d = date.today().isoformat()
    for t in top_tracks:
        tn = t.get("name", "Unknown")
        pop = t.get("popularity", 0)
        cur.execute("""
        INSERT INTO tracks_stats(date_scraped, spotify_artist_id, track_name, popularity)
        VALUES (?, ?, ?, ?)
        """, (d, artist_id, tn, pop))
    conn.commit()
    conn.close()

def update_youtube_in_artist_stats(artist_id, channel_id, subs):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    d = date.today().isoformat()
    # Chercher s'il y a déjà une ligne pour (artist_id, date)
    cur.execute("""
        SELECT id FROM artist_stats
        WHERE date_scraped = ? AND spotify_artist_id = ?
    """, (d, artist_id))
    row = cur.fetchone()
    if row:
        record_id = row[0]
        cur.execute("""
            UPDATE artist_stats
            SET youtube_channel_id = ?, youtube_subs = ?
            WHERE id = ?
        """, (channel_id, subs, record_id))
    else:
        # on insère une ligne minimaliste
        cur.execute("""
            INSERT INTO artist_stats(date_scraped, spotify_artist_id, artist_name,
                                     spotify_popularity, spotify_followers,
                                     youtube_channel_id, youtube_subs)
            VALUES (?, ?, 'UNKNOWN', NULL, NULL, ?, ?)
        """, (d, artist_id, channel_id, subs))
    conn.commit()
    conn.close()

def insert_youtube_videos(channel_id, videos_list):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    d = date.today().isoformat()

    for v in videos_list[:15]:  # Par exemple, on n'insère que les 15 premières (top vues)
        vid = v["video_id"]
        vt = v["title"]
        vc = v["view_count"]
        lk = v["like_count"]
        cm = v["comment_count"]
        cur.execute("""
        INSERT INTO youtube_videos(date_scraped, youtube_channel_id, video_id,
                                   video_title, view_count, like_count, comment_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (d, channel_id, vid, vt, vc, lk, cm))
    conn.commit()
    conn.close()

# -----------------------------------------------------------
# LECTURE POUR VISUALISATION
# -----------------------------------------------------------
def get_artist_stats(date_filter=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if date_filter:
        cur.execute("""
            SELECT date_scraped, spotify_artist_id, artist_name,
                   spotify_popularity, spotify_followers,
                   youtube_channel_id, youtube_subs
            FROM artist_stats
            WHERE date_scraped = ?
            ORDER BY artist_name
        """, (date_filter,))
    else:
        cur.execute("""
            SELECT date_scraped, spotify_artist_id, artist_name,
                   spotify_popularity, spotify_followers,
                   youtube_channel_id, youtube_subs
            FROM artist_stats
            ORDER BY date_scraped DESC, artist_name
        """)
    rows = cur.fetchall()
    conn.close()
    return rows

def get_tracks_stats(date_filter=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if date_filter:
        cur.execute("""
            SELECT date_scraped, spotify_artist_id, track_name, popularity
            FROM tracks_stats
            WHERE date_scraped = ?
            ORDER BY popularity DESC
        """, (date_filter,))
    else:
        cur.execute("""
            SELECT date_scraped, spotify_artist_id, track_name, popularity
            FROM tracks_stats
            ORDER BY date_scraped DESC, popularity DESC
        """)
    rows = cur.fetchall()
    conn.close()
    return rows

def get_youtube_videos(date_filter=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if date_filter:
        cur.execute("""
            SELECT date_scraped, youtube_channel_id, video_id, video_title,
                   view_count, like_count, comment_count
            FROM youtube_videos
            WHERE date_scraped = ?
            ORDER BY view_count DESC
        """, (date_filter,))
    else:
        cur.execute("""
            SELECT date_scraped, youtube_channel_id, video_id, video_title,
                   view_count, like_count, comment_count
            FROM youtube_videos
            ORDER BY date_scraped DESC, view_count DESC
        """)
    rows = cur.fetchall()
    conn.close()
    return rows

# -----------------------------------------------------------
# PAGE : INSÉRATION SEMI-AUTOMATIQUE POUR YOUTUBE
# -----------------------------------------------------------
def page_insertion():
    st.write("Pour ajouter les données d'un artiste, veuillez entrer son nom tel qu'il apparaît sur Spotify. "
             "Si aucune donnée pour cet artiste n'a été ajoutée aujourd'hui, celles-ci seront automatiquement insérées. "
             "Ensuite, plusieurs chaînes YouTube associées à cet artiste vous seront proposées, et vous pourrez sélectionner "
             "celle qui vous semble correcte pour l'ajouter à la base de données. "
             "Pour suivre l'évolution d'un artiste, il est important d'ajouter ses données chaque jour.")
    st.subheader("Insertion de données d'artiste")

    artist_name = st.text_input("Entrer le nom d'artiste à entrer dans la base de données :", "Booba")
    if st.button("1) Récupérer les données de l'artiste"):
        # a = True
        token = get_spotify_access_token()
        if not token:
            return
        sp_artist_id = search_spotify_artist(token, artist_name)
        if sp_artist_id is None:
            st.warning("Artiste introuvable sur Spotify.")
            return
        
        # Vérifier si on l'a déjà pour aujourd'hui
        if already_has_spotify_data_today(sp_artist_id):
            st.warning("Données Spotify déjà insérées aujourd'hui.")
        else:
            info = get_artist_info_spotify(token, sp_artist_id)
            if info:
                sp_name = info["name"]
                sp_pop = info["popularity"]
                sp_followers = info["followers"]["total"]
                insert_spotify_data(sp_artist_id, sp_name, sp_pop, sp_followers)
                top_tracks = get_artist_top_tracks(token, sp_artist_id)
                insert_spotify_tracks(sp_artist_id, top_tracks)
                st.success(f"Spotify OK : {sp_name} (pop={sp_pop}, followers={sp_followers}) inséré.")
        
        # On mémorise l'ID dans session_state pour la suite
        st.session_state["spotify_artist_id"] = sp_artist_id

        # S'il est défini, on peut lancer la recherche YouTube
        if "spotify_artist_id" in st.session_state:
            sp_id = st.session_state["spotify_artist_id"]

            # On va faire la logique "semi-automatique" :
            # - Récupérer les tracks qu'on vient d'insérer en DB pour cet artiste
            # - Chercher sur YouTube (artist + track) => accumulate channels
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            d = date.today().isoformat()
            cur.execute("""
                SELECT track_name FROM tracks_stats
                WHERE date_scraped = ? AND spotify_artist_id = ?
            """, (d, sp_id))
            track_rows = cur.fetchall()
            conn.close()
            track_names = [r[0] for r in track_rows]

            if not track_names:
                st.warning("Pas de tracks en base pour aujourd'hui (peut-être déjà insérés un autre jour ?)")
            else:
                # Cherche sur YouTube
                youtube = get_youtube_service()
                channel_counts = {}  # channel_id -> nb_occurrences
                for tn in track_names:
                    cids = search_youtube_channels_for_track(youtube, artist_name, tn)
                    for cid in cids:
                        channel_counts[cid] = channel_counts.get(cid, 0) + 1
                
                # Ensuite on récupère les subs
                all_cids = list(channel_counts.keys())
                cstats = get_channel_stats(youtube, all_cids)
                
                # On construit une liste d'objets
                channels_list = []
                for cid in all_cids:
                    occ = channel_counts[cid]
                    subs = 0
                    title = "Unknown"
                    if cid in cstats:
                        subs = cstats[cid]["subs"]
                        title = cstats[cid]["title"]
                    channels_list.append({
                        "channel_id": cid,
                        "title": title,
                        "occurrences": occ,
                        "subs": subs
                    })
                
                # On trie par (occurrences desc, subs desc)
                channels_list.sort(key=lambda x: (x["occurrences"], x["subs"]), reverse=True)
                
                # On stocke dans session_state pour l’étape suivante
                st.session_state["youtube_candidates"] = channels_list
                st.success(f"Canaux potentiels trouvés : {len(channels_list)}")

                # Affiche un aperçu
                for ch in channels_list:
                    st.write(f"- {ch['channel_id']} | {ch['title']} | occ={ch['occurrences']} | subs={ch['subs']}")
        
    # Étape 3 : L'utilisateur choisit le canal final
    if "youtube_candidates" in st.session_state:
        candidates = st.session_state["youtube_candidates"]
        if candidates:
            # On prépare un selectbox
            # On va afficher en label : "Titre (occ=x, subs=y, id=...)"
            options = [
                f"{c['title']} (occ={c['occurrences']}, subs={c['subs']}, id={c['channel_id']})"
                for c in candidates
            ]
            chosen_label = st.selectbox("Choisis le canal YouTube qui te semble correct :", options)
            
            # on retrouve le channel_id via un mapping
            label_to_cid = { 
                f"{c['title']} (occ={c['occurrences']}, subs={c['subs']}, id={c['channel_id']})": c["channel_id"]
                for c in candidates
            }
            
            chosen_cid = label_to_cid[chosen_label]
            st.write(f"Tu as choisi : {chosen_cid}")
            
            # Bouton final : insertion YouTube
            if st.button("3) Insérer la chaîne YouTube et ses vidéos"):
                # Vérif anti-doublon
                if already_has_youtube_data_today(chosen_cid):
                    st.warning("Cette chaîne est déjà enregistrée aujourd'hui.")
                else:
                    if "spotify_artist_id" not in st.session_state:
                        st.warning("Impossible de lier la chaîne car on n'a pas l'artist_id Spotify.")
                        return
                    spid = st.session_state["spotify_artist_id"]
                    
                    # Récup stats channel
                    yt = get_youtube_service()
                    cinfo = get_channel_statistics(yt, chosen_cid)
                    if cinfo:
                        subs = cinfo["subs"]
                        update_youtube_in_artist_stats(spid, chosen_cid, subs)
                        st.success(f"Chaîne mise à jour (subs={subs}) dans artist_stats.")
                        
                        # Récup toutes les vidéos
                        up_id = get_uploads_playlist_id(yt, chosen_cid)
                        if up_id:
                            all_vids = list_all_videos_in_playlist(yt, up_id)
                            if all_vids:
                                ids = [v["video_id"] for v in all_vids]
                                sdict = get_videos_stats(yt, ids)
                                for vv in all_vids:
                                    vid = vv["video_id"]
                                    stt = sdict.get(vid, {"viewCount":0,"likeCount":0,"commentCount":0})
                                    vv["view_count"] = stt["viewCount"]
                                    vv["like_count"] = stt["likeCount"]
                                    vv["comment_count"] = stt["commentCount"]
                                # tri par vues
                                all_vids.sort(key=lambda x: x["view_count"], reverse=True)
                                insert_youtube_videos(chosen_cid, all_vids)
                                st.success(f"Insertion de {len(all_vids)} vidéos (dont 15 top vues) OK !")
                            else:
                                st.warning("Aucune vidéo dans la playlist Uploads.")
                        else:
                            st.warning("Impossible de trouver la playlist Uploads de cette chaîne.")

def page_visualisation():
    st.subheader("Visualisation des données en base")
    d = st.date_input("Filtrer par date (optionnel)")
    if d:
        dstr = d.isoformat()
    else:
        dstr = None

    st.write("### Table artist_stats")
    rows = get_artist_stats(dstr)
    if rows:
        df = pd.DataFrame(rows, columns=[
            "date_scraped","spotify_artist_id","artist_name",
            "spotify_popularity","spotify_followers","youtube_channel_id","youtube_subs"
        ])
        st.dataframe(df)
    else:
        st.info("Aucune donnée dans artist_stats.")

    st.write("### Table tracks_stats")
    rows2 = get_tracks_stats(dstr)
    if rows2:
        df2 = pd.DataFrame(rows2, columns=[
            "date_scraped","spotify_artist_id","track_name","popularity"
        ])
        st.dataframe(df2)
    else:
        st.info("Aucune donnée dans tracks_stats.")

    st.write("### Table youtube_videos")
    rows3 = get_youtube_videos(dstr)
    if rows3:
        df3 = pd.DataFrame(rows3, columns=[
            "date_scraped","youtube_channel_id","video_id","video_title",
            "view_count","like_count","comment_count"
        ])
        st.dataframe(df3)
    else:
        st.info("Aucune donnée dans youtube_videos.")

def page_graphiques():
    """
    Page pour afficher des graphiques interactifs avec Plotly Express.
    """
    st.subheader("Graphiques interactifs")

    # Connexion à la base de données
    conn = sqlite3.connect(DB_NAME)

    # 1. Popularité Spotify de tous les artistes
    st.write("### Popularité Spotify et Followers Spotify")
    col1, col2 = st.columns(2)

    with col1:
        query_artists_popularity = """
            SELECT artist_name, spotify_popularity
            FROM artist_stats
            ORDER BY spotify_popularity DESC
        """
        df_artists_popularity = pd.read_sql(query_artists_popularity, conn)
        if not df_artists_popularity.empty:
            fig = px.bar(
                df_artists_popularity,
                x="artist_name",
                y="spotify_popularity",
                title="Popularité Spotify par artiste",
                labels={"spotify_popularity": "Popularité", "artist_name": "Artiste"}
            )
            st.plotly_chart(fig)
        else:
            st.info("Aucune donnée disponible pour la popularité Spotify.")

    with col2:
        query_artists_followers = """
            SELECT artist_name, spotify_followers
            FROM artist_stats
            ORDER BY spotify_followers DESC
        """
        df_artists_followers = pd.read_sql(query_artists_followers, conn)
        if not df_artists_followers.empty:
            fig = px.bar(
                df_artists_followers,
                x="artist_name",
                y="spotify_followers",
                title="Followers Spotify par artiste",
                labels={"spotify_followers": "Followers", "artist_name": "Artiste"}
            )
            st.plotly_chart(fig)
        else:
            st.info("Aucune donnée disponible pour les followers Spotify.")

    st.markdown("---")

    # Choix de l'artiste pour les deux derniers graphiques
    st.write("### Top 10 morceaux Spotify et vidéos YouTube")

    # Récupérer la liste des artistes et ajouter "Tous les artistes"
    query_artists = "SELECT DISTINCT artist_name FROM artist_stats"
    artist_list = pd.read_sql(query_artists, conn)["artist_name"].tolist()
    artist_list.insert(0, "Tous les artistes")  # Ajoute l’option "Tous les artistes"
    selected_artist = st.selectbox("Choisissez un artiste :", artist_list)

    col1, col2 = st.columns(2)

    with col1:
        # Filtrer les morceaux Spotify selon l'artiste choisi
        if selected_artist == "Tous les artistes":
            query_tracks = """
                SELECT track_name, popularity, artist_name
                FROM tracks_stats
                JOIN artist_stats ON tracks_stats.spotify_artist_id = artist_stats.spotify_artist_id
                ORDER BY popularity DESC
                LIMIT 10
            """
        else:
            query_tracks = f"""
                SELECT track_name, popularity, artist_name
                FROM tracks_stats
                JOIN artist_stats ON tracks_stats.spotify_artist_id = artist_stats.spotify_artist_id
                WHERE artist_name = '{selected_artist}'
                ORDER BY popularity DESC
                LIMIT 10
            """
        df_tracks = pd.read_sql(query_tracks, conn)
        if not df_tracks.empty:
            # On construit l'ordre des catégories (du plus populaire au moins populaire), sans doublons
            ordered_categories_tracks = (
                df_tracks
                .sort_values("popularity", ascending=False)["track_name"]
                .unique()
                .tolist()
            )
            # On crée les catégories "track_name"
            df_tracks["track_name"] = pd.Categorical(
                df_tracks["track_name"],
                categories=ordered_categories_tracks,
                ordered=True
            )
            
            fig = px.bar(
                df_tracks,
                x="track_name",
                y="popularity",
                color="artist_name",
                title=f"Top 10 morceaux Spotify ({selected_artist})",
                labels={"popularity": "Popularité", "track_name": "Titre", "artist_name": "Artiste"},
                category_orders={"track_name": ordered_categories_tracks}
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig)
        else:
            st.info(f"Aucune donnée disponible pour {selected_artist}.")

    with col2:
        # Filtrer les vidéos YouTube selon l'artiste choisi
        if selected_artist == "Tous les artistes":
            query_videos = """
                SELECT video_title, view_count, artist_name
                FROM youtube_videos
                JOIN artist_stats ON youtube_videos.youtube_channel_id = artist_stats.youtube_channel_id
                ORDER BY view_count DESC
                LIMIT 10
            """
        else:
            query_videos = f"""
                SELECT video_title, view_count, artist_name
                FROM youtube_videos
                JOIN artist_stats ON youtube_videos.youtube_channel_id = artist_stats.youtube_channel_id
                WHERE artist_name = '{selected_artist}'
                ORDER BY view_count DESC
                LIMIT 10
            """
        df_videos = pd.read_sql(query_videos, conn)
        if not df_videos.empty:
            ordered_categories_videos = (
                df_videos
                .sort_values("view_count", ascending=False)["video_title"]
                .unique()
                .tolist()
            )
            df_videos["video_title"] = pd.Categorical(
                df_videos["video_title"],
                categories=ordered_categories_videos,
                ordered=True
            )
            fig = px.bar(
                df_videos,
                x="video_title",
                y="view_count",
                color="artist_name",
                title=f"Top 10 vidéos YouTube ({selected_artist})",
                labels={"view_count": "Vues", "video_title": "Titre", "artist_name": "Artiste"},
                category_orders={"video_title": ordered_categories_videos}
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig)
        else:
            st.info(f"Aucune donnée disponible pour {selected_artist}.")

    # Fermeture de la connexion
    conn.close()

def page_evolution():
    """
    Page pour afficher l'évolution des statistiques d'un artiste par jour.
    """
    st.subheader("Évolution des statistiques d'un artiste")

    # Connexion à la base de données
    conn = sqlite3.connect(DB_NAME)

    # Récupérer la liste des artistes
    query_artists = "SELECT DISTINCT artist_name FROM artist_stats"
    artist_list = pd.read_sql(query_artists, conn)["artist_name"].tolist()

    # Sélection d'un artiste
    selected_artist = st.selectbox("Choisissez un artiste :", artist_list)

    if selected_artist:
        # Requête pour récupérer les données d'évolution
        query_artist_evolution = f"""
            SELECT date_scraped, spotify_popularity, spotify_followers, youtube_subs
            FROM artist_stats
            WHERE artist_name = '{selected_artist}'
            ORDER BY date_scraped ASC
        """
        df_evolution = pd.read_sql(query_artist_evolution, conn)

        if not df_evolution.empty:
            # Convertir la colonne date_scraped en datetime.date pour uniformiser les dates
            df_evolution["date_scraped"] = pd.to_datetime(df_evolution["date_scraped"]).dt.date

            # Vérification : Afficher les données pour débogage
            st.write("### Données récupérées pour l'évolution")
            st.dataframe(df_evolution)

            # Graphique de l'évolution de la popularité Spotify
            st.write(f"### Évolution de la popularité Spotify pour {selected_artist}")
            fig_popularity = px.line(
                df_evolution,
                x="date_scraped",
                y="spotify_popularity",
                title=f"Évolution de la popularité Spotify de {selected_artist}",
                labels={"date_scraped": "Date", "spotify_popularity": "Popularité"},
                markers=True
            )
            st.plotly_chart(fig_popularity)

            # Graphique de l'évolution des followers Spotify
            st.write(f"### Évolution des followers Spotify pour {selected_artist}")
            fig_followers = px.line(
                df_evolution,
                x="date_scraped",
                y="spotify_followers",
                title=f"Évolution des followers Spotify de {selected_artist}",
                labels={"date_scraped": "Date", "spotify_followers": "Followers"},
                markers=True
            )
            st.plotly_chart(fig_followers)

            # Graphique de l'évolution des abonnés YouTube
            st.write(f"### Évolution des abonnés YouTube pour {selected_artist}")
            fig_youtube_subs = px.line(
                df_evolution,
                x="date_scraped",
                y="youtube_subs",
                title=f"Évolution des abonnés YouTube de {selected_artist}",
                labels={"date_scraped": "Date", "youtube_subs": "Abonnés YouTube"},
                markers=True
            )
            st.plotly_chart(fig_youtube_subs)

        else:
            st.info(f"Aucune donnée disponible pour {selected_artist}.")
    
    # Fermeture de la connexion
    conn.close()


import streamlit as st



def main():
    init_db()
    st.markdown("<h1 style='text-align: center;'>🎵 Musify Insights</h1>", unsafe_allow_html=True)

# Centrer le contenu avec des colonnes
col1, col2, col3 = st.columns([1, 3, 1])  # Utilisation de colonnes pour centrer le contenu

# Placer l'image dans la colonne du milieu
with col2:
    st.image("image.png", width=150, use_column_width=False)  # Ajuster la taille ici

# Placer le texte centré en dessous de l'image
with col2:
    st.markdown("""
    <style>
        .header-container {
            display: flex;
            justify-content: center;
            align-items: center;
            flex-direction: column;
            text-align: center;
            margin-top: 50px;
        }
        .header-container img {
            margin: 0 auto;
            display: block;
        }
        .header-text {
            font-size: 1.5em;
            margin-top: 20px;
        }
        .logo img {
            width: 150px;
            height: auto;
        }
        .header-text {
            color: white;
            font-size: 24px;
            max-width: 600px;
            margin-top: 20px;
        }
    </style>
    <div class="header-container">
        <div class="header-text">
            <h1>🎵Musify Insights</h1>
        <p>Bienvenue dans l'application <strong>🎵Musify Insights</strong> :</p>
        <ul style="list-style-type: none; padding: 0;">
            <li>Suivez la <strong>popularité Spotify</strong> des artistes</li>
            <li>Explorez leurs <strong>meilleures pistes</strong> et vidéos YouTube</li>
            <li>Visualisez les <strong>tendances</strong> sur le long terme</li>
            <li>Créez des graphiques et des tableaux interactifs</li>
        </ul>   
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Utilisation de la classe pour le conteneur principal
    with st.container():
        # Utilisation d'un espace pour aérer la mise en page
        st.markdown("---")
        tab1, tab2, tab3, tab4 = st.tabs(["Insertion", "Visualisation", "Graphiques", "Évolution"])
        
        with tab1:
            page_insertion()
        with tab2:
            page_visualisation()
        with tab3:
            page_graphiques()
        with tab4:
            page_evolution()

if __name__ == "__main__":
    main()