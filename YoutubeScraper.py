from googleapiclient.discovery import build
import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu
import io
import time
import html
from datetime import datetime
from zoneinfo import ZoneInfo

api_key = st.secrets["api_key"]
youtube = build('youtube', 'v3', developerKey=api_key)


def scrape_youtube_search(query, 
                      max_total_results=500, 
                      published_after=None,
                      published_before=None,
                      order=None,
                      region_code=None
                      ):

    youtube = build('youtube', 'v3', developerKey=api_key)
    max_results_per_page = 50
    all_results = []
    next_page_token = None
    total_fetched = 0
    video_ids = []

    # Step 1: Collect video info and IDs
    while True:
        # Build params dict dynamically
        params = {
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": max_results_per_page,
        }
        if next_page_token:
            params["pageToken"] = next_page_token
        if published_after:
            params["publishedAfter"] = published_after
        if published_before:
            params["publishedBefore"] = published_before
        if order:
            params["order"] = order
        if region_code:
            params["regionCode"] = region_code

        request = youtube.search().list(**params)
        response = request.execute()

        for item in response['items']:
            if item['id'].get('kind') == 'youtube#video' and 'videoId' in item['id']:
                video_id = item['id']['videoId']
                title = html.unescape(item['snippet']['title'])
                url = f"https://www.youtube.com/watch?v={video_id}"
                channel = html.unescape(item['snippet']['channelTitle'])
                published_at_raw = item['snippet']['publishedAt']
                try:
                    dt_utc = datetime.strptime(published_at_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=ZoneInfo("UTC"))
                    dt_gmt7 = dt_utc.astimezone(ZoneInfo("Asia/Jakarta"))
                    published_at = dt_gmt7.strftime("%d-%m-%Y %H:%M:%S")
                except Exception:
                    published_at = published_at_raw

                all_results.append({
                    'Title': title,
                    'Video ID': video_id,
                    'URL': url,
                    'Channel': channel,
                    'Published At': published_at
                })
                video_ids.append(video_id)
                total_fetched += 1

        next_page_token = response.get('nextPageToken')
        if not next_page_token or total_fetched >= max_total_results:
            break
        time.sleep(0.1)

    # Step 2: Batch fetch statistics (views, likes comments)
    stats_dict = {}
    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i+50]
        stats_request = youtube.videos().list(
            id=','.join(batch_ids),
            part='statistics'
        )
        stats_response = stats_request.execute()
        for item in stats_response['items']:
            vid = item['id']
            statistics = item['statistics']

            views = statistics.get('viewCount', 'N/A')
            likes = statistics.get('likeCount', 'N/A')
            comments = statistics.get('commentCount', 'N/A')

            stats_dict[vid] = {
            'Views': views,
            'Likes': likes,
            'Comments': comments
            }
        time.sleep(0.1)

    # Step 3: Add statistics to results
    for row in all_results:
        video_id = row['Video ID']
        stats = stats_dict.get(video_id, {})
        row['Views'] = stats.get('Views', 'N/A')
        row['Likes'] = stats.get('Likes', 'N/A')
        row['Comments'] = stats.get('Comments', 'N/A')

    return pd.DataFrame(all_results)

# ================================
# STREAMLIT UI
# ================================
st.set_page_config(page_title="Youtube API Scraper", layout="centered")

# Sidebar Navigation
with st.sidebar:
    menu = option_menu(
        menu_title="Main Menu",
        options=["How to use", "Youtube Scraper", "About"],
        icons=["question-circle-fill", "search", "diagram-3"],
        menu_icon="cast",  # optional
        default_index=1,  # optional
        styles={
            "icon": {"color": "orange"},
            "nav-link": {
                "--hover-color": "#eee",
            },
            "nav-link-selected": {"background-color": "green"},
        },
    )

if menu == "Youtube Scraper":
    st.title("🔴 YouTube Scraper")
    st.markdown("Masukkan kata kunci pencarian untuk mengambil data video dari YouTube.")
    st.markdown("Jumlah maksimal result adalah 500 video. Untuk lebih banyak result, bisa gunakan ")

    with st.container(border=True):
        query = st.text_area("Keyword pencarian video* (Required)", height=68)
        
        # Optional filters
        col1, col2 = st.columns(2)
        with col1:
            published_after_date = st.date_input("Published After (start date)", value=None)
        with col2:
            published_before_date = st.date_input("Published Before (end date)", value=None)

        order = st.selectbox(
            "Order by",
            ["", "date", "rating", "relevance", "title", "viewCount"],
            format_func=lambda x: "Default" if x == "" else x.capitalize()
        )
        region_code = st.text_input("Region Code (e.g. US, ID)", "")

        run_scraper = False
        if query.strip():
            run_scraper = st.button("Jalankan")

    if query.strip() and run_scraper:
        # Convert dates to ISO 8601 if selected
        published_after = None
        if published_after_date:
            published_after = datetime.combine(published_after_date, datetime.min.time()).strftime("%Y-%m-%dT%H:%M:%SZ")
        published_before = None
        if published_before_date:
            published_before = datetime.combine(published_before_date, datetime.max.time()).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Call the scraper with optional filters
        with st.spinner("Mengambil data dari YouTube..."):
            results_df = scrape_youtube_search(
                query,
                published_after=published_after,
                published_before=published_before,
                order=order or None,
                region_code=region_code or None
            )
            st.dataframe(results_df)

            # Provide a download button
            to_download = io.BytesIO()
            results_df.to_excel(to_download, index=False)
            to_download.seek(0)

            st.download_button(
                "📥 Download Excel",
                data=to_download,
                file_name="youtube_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.success(f"✅ Selesai! {len(results_df)} video ditemukan dan dapat diunduh.")

elif menu == "How to use":
    st.title("📖 How to Use")
    st.markdown("""
    ### Petunjuk Penggunaan

    1. Input keyword pencarian video
    2. Klik **Jalankan**, tunggu hingga proses selesai.
    3. Jika berhasil, hasil scraping bisa langsung diunduh dalam format **Excel**.
    """)

elif menu == "About":
    st.title("ℹ️ About")
    st.markdown("""
    ### Burson Youtube Scraper v0.0.1

    **Release Note:**
    - ✅ Basic scraping untuk Youtube

    **Made by**: Naomi 
    """)
