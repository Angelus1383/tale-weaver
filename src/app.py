import base64
import json
import streamlit as st
import warnings
import tale_weaver.utils.pdf_generator as pdf
import os

from dotenv import load_dotenv
from html import escape
from pathlib import Path
from tale_weaver.crew import TaleWeaver

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

load_dotenv()

st.set_page_config(page_title="Tale Weaver", layout="wide")

# ---------- CSS ----------
PAGE_CSS = """
<style>

@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:wght@400;700&display=swap');

/* reduce white space over content */
div.block-container { padding-top: 35px !important; }
header {
    height: 40px !important;
    min-height: 40px !important;
}

/* reduce title margin */
h1 { margin-top: 0px !important; margin-bottom: 0.75rem !important; }
:root { --page-w: 520px; --page-h: 710px; }
.flip { display:flex; gap:10px; justify-content:center; align-items:flex-start; }
.page {
  width: var(--page-w);
  height: var(--page-h);
  background: #f5eedd;
  border-radius: 10px;
  box-shadow: 0 10px 30px rgba(0,0,0,.15);
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(0,0,0,.06);
}

.page.image, .page.cover {
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color:#000;
}
.page.cover { margin-inline: auto; }

.page.image img, .page.cover img {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  display: block;
  background: #f5eedd;
  border-radius: 10px;
}

.page.text { display:flex; align-items:center; justify-content:center; padding:40px 48px; color:#000; font-family: 'EB Garamond', serif; line-height: 1.6;}
.page.text .content { max-width:95%; line-height:1.9; font-size:1.22rem; text-align:justify; hyphens:auto; }
.page.text .content p::first-letter {
  font-size:5.4rem; line-height:.8; font-weight:800; float:left; margin-right:14px;
  font-family: Georgia, "Times New Roman", serif;
}
.page .num { position:absolute; bottom:14px; right:18px; opacity:.55; font-size:.95rem; }

.st-key-prev, .st-key-next { height: var(--page-h) !important; }

.st-key-prev .stButton, .st-key-next .stButton { height:100% !important; display:flex; }
.st-key-prev .stButton > div, .st-key-next .stButton > div { flex:1; display:flex; }
.st-key-prev .stButton button, .st-key-next .stButton button {
  flex:1; height:100% !important; width:100% !important; border-radius:8px !important; font-size: 2rem;
}


/* fallback responsive: su schermi più stretti torna alla larghezza precedente */
@media (max-width: 1400px){
  :root{ --page-w: 560px; }
}
</style>
"""
st.markdown(PAGE_CSS, unsafe_allow_html=True)

# ---------- Helpers ----------
def to_data_uri(img_path: str):
    if not img_path:
        return None
    p = Path(img_path)
    if not p.exists():
        return None
    ext = p.suffix.lower().replace(".", "")
    if ext not in {"png","jpg","jpeg","webp","gif"}:
        ext = "png"
    try:
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            return f"data:image/{ext};base64,{b64}"
    except Exception:
        return None

def build_pages(data: dict):
    pages = []
    pages.append({"kind":"cover", "image": data.get("storybook_image_path"), "title": data.get("storybook_title", "")})
    for pg in data.get("pages", []):
        pages.append({"kind":"image", "image": pg.get("scene_image_path"), "n": pg.get("page_number")})
        pages.append({"kind":"text",  "text": pg.get("scene_text",""), "n": pg.get("page_number")})
    return pages

def image_page_html(img_path: str, cover=False):
    uri = to_data_uri(img_path)
    if uri is None:
        body = f'<div style="display:flex;height:100%;align-items:center;justify-content:center;opacity:.7;padding:24px;text-align:center;">Immagine non trovata<br><small>{escape(str(img_path) or "")}</small></div>'
    else:
        body = f'<img src="{uri}" alt="">'
    if cover:
        return f'<div class="page cover">{body}</div>'
    else:
        return f'<div class="page image">{body}</div>'

def text_page_html(text: str, page_num: int):
    safe = escape(text or "").replace("\n\n", "</p><p>").replace("\n", "<br>")
    return f'<div class="page text"><div class="content"><p>{safe}</p></div><div class="num">{page_num}</div></div>'

def page_to_html(pobj, idx):
    if pobj["kind"] in {"cover","image"}:
        return image_page_html(pobj.get("image"), cover=(pobj["kind"]=="cover"))
    else:
        return text_page_html(pobj.get("text",""), idx)
    
def render_spread(pages, current_page: int):
    total = len(pages)
    if current_page == 1:
        html = image_page_html(pages[0].get("image"), cover=True)
        st.markdown(html, unsafe_allow_html=True)
        return

    left_idx  = current_page if current_page % 2 == 0 else current_page - 1
    right_idx = left_idx + 1 if left_idx + 1 <= total else None

    left_html  = page_to_html(pages[left_idx - 1],  left_idx)
    right_html = page_to_html(pages[right_idx - 1], int(left_idx/2)) if right_idx else ""

    spread = f'<div class="flip">{left_html}{right_html}</div>'
    st.markdown(spread, unsafe_allow_html=True)

def generate_storybook(payload: dict) -> dict:
    output = TaleWeaver().crew().kickoff(inputs=payload)
    json_data = output.to_dict()
    
    with open(os.path.join(os.getenv("OUTPUT_DIR", "./"), "".join([json_data.get("storybook_title", "storybook"),".json"])), "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    pdf.generate_storybook_pdf(json_data, os.path.join(os.getenv("OUTPUT_DIR", "./"), "".join([json_data.get("storybook_title", "storybook"),".pdf"])))
    return json_data

# ---------- STATE ----------
if "page" not in st.session_state:
    st.session_state.page = 1
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "api_result" not in st.session_state:
    st.session_state.api_result = None
if "pages" not in st.session_state:
    st.session_state.pages = []
if "total_pages" not in st.session_state:
    st.session_state.total_pages = 0

# ---------- FORM CREATE STORYBOOK ----------
if not st.session_state.submitted:
    st.title("📖 Tale Weaver 📖")

    with st.form("start_form"):
        st.subheader("Create a Storybook")
        topic = st.text_area("Topic Description", height=80, placeholder="Write here…")
        language = st.selectbox("Language", ["English", "Italian", "French", "German"], index=1)
        page_count_input = st.number_input("Page number", value=10, placeholder="Type a number...", min_value=1, max_value=20)
        sent = st.form_submit_button("Submit")
    if sent:
        payload = {
            "topic": topic,
            "language": language,
            "pageCount": int(page_count_input),
            "penultimatePage": int(page_count_input-1)
        }
        try:
            with st.spinner("Generating Storybook…"):
                res = generate_storybook(payload)
        except Exception as e:
            st.error(f"An error occurs during call: {e}")
            st.stop()

        st.session_state.api_result = res
        st.session_state.pages = build_pages(res)
        st.session_state.total_pages = len(st.session_state.pages)

        st.session_state.form_text = topic
        st.session_state.form_mode = language
        st.session_state.page = 1
        st.session_state.submitted = True
        st.rerun()  

    # --- FORM OPEN EXISTING STORYBOOK ---
    outdir = os.getenv("OUTPUT_DIR", "./")
    json_list = sorted([p.name.replace(".json", "") for p in Path(outdir).glob("*.json")])

    with st.form("open_existing"):
        st.subheader("See an existing Storybook")
        if not json_list:
            st.info("No Storybook has been created yet.")
            open_clicked = False
            selected_json = None
            dl_clicked = False
        else:
            selected_json = st.selectbox("Select a Storybook:", options=json_list, index=0)
        c_open, c_dl, sp_l, sp_r = st.columns([2, 2, 3, 5])
        with c_open:
            open_clicked = st.form_submit_button("Open Storybook")
        with c_dl:
            dl_clicked = st.form_submit_button("Download PDF")
            
                
    # Download selected Storybook
    if dl_clicked and selected_json:
        pdf_path = (Path(outdir) / selected_json).with_suffix(".pdf")
        if pdf_path.exists():
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "⬇️ Download selected PDF",
                    data=f,
                    file_name=pdf_path.name,
                    mime="application/pdf",
                    use_container_width=True,
                )
        else:
            st.warning(f"PDF not found: {selected_json.replace('.json', '.pdf')}")
    # Open selected Storybook
    if open_clicked and selected_json:
        try:
            with open(Path(outdir) / "".join([selected_json, ".json"]), "r", encoding="utf-8") as f:
                res = json.load(f)
        except Exception as e:
            st.error(f"An error occurs loading the JSON file: {e}")
            st.stop()

        st.session_state.api_result = res
        st.session_state.pages = build_pages(res)
        st.session_state.total_pages = len(st.session_state.pages)
        st.session_state.page = 1
        st.session_state.submitted = True
        st.rerun()

    st.stop()

# ---------- FLIPBOOK ----------
pages = st.session_state.pages
total_pages = st.session_state.total_pages

if not pages:
    st.info("No content to show. Please return to the form and then send a request.")
    st.stop()

col_l, col_c, col_r = st.columns([1, 15, 1], gap="large")

with col_l:
    st.button("⟵", key="prev", disabled=(st.session_state.page <= 1), use_container_width=True)

with col_c:
    # lo spread vero e proprio
    page_slot = st.container()
    with page_slot:
        if len(pages) > 0: 
            render_spread(pages, st.session_state.page)

with col_r:
    st.button("⟶", key="next", disabled=(st.session_state.page >= total_pages), use_container_width=True)

if st.button("⬅️ Create a new Storybook", use_container_width=True, key="back-home"):
    st.session_state.submitted = False
    st.session_state.page = 1
    st.rerun()

# Logica dei click (uguale alla tua, ma qui dopo i bottoni)
if st.session_state.get("prev"):
    st.session_state.page = max(1, st.session_state.page - 2)
    st.rerun()
if st.session_state.get("next"):
    st.session_state.page = min(total_pages, st.session_state.page + 2)
    st.rerun()
