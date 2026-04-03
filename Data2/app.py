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
FONT_FILENAME = 'AlibabaPuHuiTi-3-65-Medium.ttf'  # 请确保 GitHub 上文件名完全一致
font_path = os.path.join(current_dir, FONT_FILENAME)

if os.path.exists(font_path):
    prop = fm.FontProperties(fname=font_path, size=12)
    prop_title = fm.FontProperties(fname=font_path, size=18)
    font_available = True
else:
    st.warning(f"⚠️ 未找到字体文件 {FONT_FILENAME}，将使用系统默认字体。")
    prop = fm.FontProperties(size=12)
    prop_title = fm.FontProperties(size=18)
    font_available = False

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

# --- 模式 1：A列为数字题号 ---
def parse_mode_id(df):
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

# --- 模式 2：A列为题目文本（您上传的文件格式） ---
def parse_mode_title(df):
    questions = []
    curr_title, curr_opts = None, []

    for _, row in df.iterrows():
        col0 = row[0]
        col1 = row[1]
        col2 = row[2]
        
        # 如果A列不为空，说明是一个新题目开始
        if pd.notna(col0) and str(col0).strip() != "":
            if curr_title and curr_opts:
                questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
            curr_title = str(col0).strip()
            curr_opts = []
            
        # 如果有题目且B列不为空，记录选项
        if curr_title and pd.notna(col1):
            try:
                val_str = str(col2).strip().replace('%', '')
                val = float(val_str)
                curr_opts.append([str(col1), val])
            except: pass

    if curr_title and curr_opts:
        questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
    return questions

def main():
    st.set_page_config(page_title="数据可视化工具", layout="wide")
    st.title("📊 交叉表数据可视化")
    
    col_file, col_mode = st.columns([2, 1])
    
    with col_file:
        uploaded_file = st.file_uploader("第一步：上传您的 Excel 或 CSV 文件", type=["csv", "xlsx", "xls"])
    
    with col_mode:
        mode = st.radio("第二步：选择表格布局模式", 
                        ["自动/题号模式 (A列是1,2,3...)", 
                         "题目模式 (A列是具体题目文本)"])

    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file, header=None) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file, header=None)
            
            if "题目模式" in mode:
                parsed_questions = parse_mode_title(df)
            else:
                parsed_questions = parse_mode_id(df)

            if not parsed_questions:
                st.error("未能识别出题目，请尝试切换布局模式或检查文件。")
            else:
                st.success(f"识别到 {len(parsed_questions)} 个题目")
                charts_for_export = []
                
                for i, q in enumerate(parsed_questions):
                    st.divider()
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        st.write(f"**Q{i+1}:** {q['title']}")
                        ctype = st.selectbox(f"选择类型", ["条形图", "柱状图", "饼图"], key=f"sel_{i}")
                    
                    with c2:
                        fig, ax = plt.subplots(figsize=(11, 7))
                        ax.set_title(q['title'], fontproperties=prop_title, pad=25)
                        
                        data = q['data']
                        if ctype == "条形图":
                            wrapped_labels = [smart_wrap(l, 35) for l in data['Option']]
                            bars = ax.barh(wrapped_labels, data['Value'], color='#4285F4')
                            ax.invert_yaxis()
                            # 彻底解决乱码：为坐标轴标签设置字体
                            for t in ax.get_yticklabels(): t.set_fontproperties(prop)
                            for t in ax.get_xticklabels(): t.set_fontproperties(prop)
                            # 解决溢出：增加右侧范围
                            ax.set_xlim(0, max(data['Value']) * 1.15 if not data['Value'].empty else 100)
                            for bar in bars:
                                ax.text(bar.get_width(), bar.get_y()+bar.get_height()/2, f" {bar.get_width():.1f}%", va='center', fontproperties=prop)
                        
                        elif ctype == "柱状图":
                            wrapped_labels = [smart_wrap(l, 12) for l in data['Option']]
                            bars = ax.bar(wrapped_labels, data['Value'], color='#34A853')
                            for t in ax.get_xticklabels(): t.set_fontproperties(prop)
                            for t in ax.get_yticklabels(): t.set_fontproperties(prop)
                            ax.set_ylim(0, max(data['Value']) * 1.15 if not data['Value'].empty else 100)
                            for bar in bars:
                                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height(), f"{bar.get_height():.1f}%", va='bottom', ha='center', fontproperties=prop)
                        
                        elif ctype == "饼图":
                            wedges, texts, autotexts = ax.pie(data['Value'], labels=data['Option'], autopct='%1.1f%%', startangle=90)
                            plt.setp(texts, fontproperties=prop)
                            plt.setp(autotexts, fontproperties=prop, color='white')

                        plt.tight_layout()
                        buf = io.BytesIO()
                        fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
                        st.image(buf)
                        charts_for_export.append({"title": q['title'], "buffer": buf})
                        plt.close(fig)

                if charts_for_export:
                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, "a") as f:
                        for c in charts_for_export:
                            c['buffer'].seek(0)
                            safe_name = "".join([x for x in c['title'] if x.isalnum() or x in (' ', '_')])[:20]
                            f.writestr(f"{safe_name}.png", c['buffer'].read())
                    st.download_button("📥 下载所有图表", zip_buf.getvalue(), "charts.zip")
        except Exception as e:
            st.error(f"处理出错: {e}")

if __name__ == "__main__":
    main()
