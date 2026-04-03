import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.font_manager as fm
import io
import zipfile
import os

# --- 1. 字体安全加载逻辑 ---
current_dir = os.path.dirname(__file__)
FONT_FILENAME = 'Alibaba.ttf'  # 请确保 GitHub 上文件名完全一致
font_path = os.path.join(current_dir, FONT_FILENAME)

# 初始化字体属性变量
if os.path.exists(font_path):
    try:
        # 直接创建属性对象，但不去调用 get_name()，避免触发 ft2font 崩溃
        prop = fm.FontProperties(fname=font_path, size=12)
        prop_title = fm.FontProperties(fname=font_path, size=18)
        font_available = True
    except Exception as e:
        st.error(f"字体文件加载失败: {e}")
        font_available = False
else:
    st.warning(f"未找到字体文件 {FONT_FILENAME}。")
    font_available = False

# 如果加载失败，回退到系统默认
if not font_available:
    prop = fm.FontProperties(size=12)
    prop_title = fm.FontProperties(size=18)

plt.rcParams['axes.unicode_minus'] = False 

def smart_wrap(text, width):
    text = str(text)
    lines = []
    for para in text.split('\n'):
        curr_line, curr_width = '', 0
        for char in para:
            w = 2 if '\u4e00' <= char <= '\u9fff' else 1
            if curr_width + w > width:
                lines.append(curr_line)
                curr_line, curr_width = char, w
            else:
                curr_line += char
                curr_width += w
        lines.append(curr_line)
    return '\n'.join(lines)

def parse_questions_new(df):
    questions = []
    df_subset = df.iloc[:, [0, 1, 2]].copy()
    df_subset.columns = ['col_0', 'col_1', 'col_2']
    curr_title, curr_opts = None, []

    for _, row in df_subset.iterrows():
        q_num = str(row['col_0'])
        is_new = pd.notna(pd.to_numeric(q_num, errors='coerce'))
        if is_new and pd.notna(row['col_1']):
            if curr_title and curr_opts:
                questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
            curr_title, curr_opts = row['col_1'], []
        elif curr_title and pd.notna(row['col_1']):
            try:
                val = float(str(row['col_2']).strip().replace('%', ''))
                curr_opts.append([row['col_1'], val])
            except: pass
    if curr_title and curr_opts:
        questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
    return questions

def main():
    st.title("📊 数据可视化工具")
    uploaded_file = st.file_uploader("上传 Excel/CSV", type=["csv", "xlsx", "xls"])

    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file, header=None) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file, header=None)
            parsed_questions = parse_questions_new(df)

            if parsed_questions:
                charts_for_export = []
                for i, q in enumerate(parsed_questions):
                    st.subheader(f"Q: {q['title']}")
                    ctype = st.selectbox("类型", ["条形图", "柱状图", "饼图"], key=f"c_{i}")
                    
                    fig, ax = plt.subplots(figsize=(10, 6))
                    # --- 核心：显式指定 fontproperties ---
                    ax.set_title(q['title'], fontproperties=prop_title)
                    
                    data = q['data']
                    if ctype == "条形图":
                        labels = [smart_wrap(l, 25) for l in data['Option']]
                        bars = ax.barh(labels, data['Value'], color='#4285F4')
                        ax.invert_yaxis()
                        # 给刻度设置字体
                        for label in ax.get_yticklabels(): label.set_fontproperties(prop)
                        for bar in bars:
                            ax.text(bar.get_width(), bar.get_y()+bar.get_height()/2, f" {bar.get_width():.1f}%", va='center', fontproperties=prop)
                    
                    elif ctype == "柱状图":
                        labels = [smart_wrap(l, 10) for l in data['Option']]
                        bars = ax.bar(labels, data['Value'], color='#34A853')
                        for label in ax.get_xticklabels(): label.set_fontproperties(prop)
                        for bar in bars:
                            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height(), f"{bar.get_height():.1f}%", va='bottom', ha='center', fontproperties=prop)
                    
                    elif ctype == "饼图":
                        wedges, texts, autotexts = ax.pie(data['Value'], labels=data['Option'], autopct='%1.1f%%')
                        # 饼图必须手动循环设置每个文本的字体
                        plt.setp(texts, fontproperties=prop)
                        plt.setp(autotexts, fontproperties=prop)

                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
                    st.image(buf)
                    charts_for_export.append({"t": q['title'], "b": buf})
                    plt.close(fig)

                if charts_for_export:
                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, "a") as f:
                        for c in charts_for_export:
                            c['b'].seek(0)
                            f.writestr(f"{c['t']}.png", c['b'].read())
                    st.download_button("下载全部图表", zip_buf.getvalue(), "charts.zip")
        except Exception as e:
            st.error(f"处理出错: {e}")

if __name__ == "__main__":
    main()
