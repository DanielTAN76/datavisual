import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.font_manager as fm
import io
import zipfile
import os

# --- 1. 字体安全加载逻辑 (保持最稳健版本) ---
current_dir = os.path.dirname(__file__)
FONT_FILENAME = 'AlibabaPuHuiTi-3-65-Medium.ttf'  
font_path = os.path.join(current_dir, FONT_FILENAME)

# 初始化字体属性
prop = fm.FontProperties(size=12)
prop_title = fm.FontProperties(size=18)
font_available = False

if os.path.exists(font_path):
    try:
        # 仅尝试加载，不调用 get_name() 防止 0x55 崩溃
        prop = fm.FontProperties(fname=font_path, size=12)
        prop_title = fm.FontProperties(fname=font_path, size=18)
        font_available = True
    except Exception as e:
        st.error(f"字体加载失败: {e}。将使用系统默认字体。")

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

# --- 内部解析器 A：题号模式 ---
def _parse_by_id(df):
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

# --- 内部解析器 B：题目模式 ---
def _parse_by_title(df):
    questions = []
    curr_title, curr_opts = None, []
    for _, row in df.iterrows():
        col0, col1, col2 = row[0], row[1], row[2]
        if pd.notna(col0) and str(col0).strip() != "":
            if curr_title and curr_opts:
                questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
            curr_title = str(col0).strip()
            curr_opts = []
        if curr_title and pd.notna(col1):
            try:
                val = float(str(col2).strip().replace('%', ''))
                curr_opts.append([str(col1), val])
            except: pass
    if curr_title and curr_opts:
        questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
    return questions

# --- 核心：自动识别模式逻辑 ---
def auto_parse_file(df):
    # 获取 A 列前 10 个非空值进行分析
    sample_a = df[0].dropna().head(10).astype(str).tolist()
    if not sample_a:
        return []

    # 检查 A 列样本是否主要是纯数字
    numeric_count = 0
    for val in sample_a:
        if pd.to_numeric(val, errors='coerce') is not None:
            numeric_count += 1
    
    # 启发式规则：如果超过一半的非空单元格是数字，认为是题号模式
    if numeric_count / len(sample_a) > 0.5:
        st.toast("🤖 检测到【题号模式】数据布局")
        return _parse_by_id(df)
    else:
        st.toast("🤖 检测到【题目模式】数据布局")
        return _parse_by_title(df)

def main():
    st.set_page_config(page_title="全自动数据可视化", layout="wide")
    st.title("📊 全自动交叉表分析工具")
    
    uploaded_file = st.file_uploader("上传您的 Excel 或 CSV 文件", type=["csv", "xlsx", "xls"])

    if uploaded_file:
        try:
            # 读取数据
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, header=None)
            else:
                df = pd.read_excel(uploaded_file, header=None)
            
            # 自动识别并解析
            with st.spinner('正在智能分析数据结构...'):
                parsed_questions = auto_parse_file(df)

            if not parsed_questions:
                st.error("未能识别出题目，请确保 A 列为题号或题目，B 列为选项，C 列为数据。")
            else:
                st.success(f"自动识别成功！共找到 {len(parsed_questions)} 个题目")
                
                charts_for_export = []
                for i, q in enumerate(parsed_questions):
                    st.divider()
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        st.write(f"**Q{i+1}:**")
                        st.write(q['title'])
                        ctype = st.selectbox(f"选择图表类型", ["条形图", "柱状图", "饼图"], key=f"sel_{i}")
                    
                    with c2:
                        fig, ax = plt.subplots(figsize=(11, 7))
                        ax.set_title(q['title'], fontproperties=prop_title, pad=25)
                        
                        data = q['data']
                        if data.empty:
                            st.warning("该题目无有效数据")
                            continue

                        if ctype == "条形图":
                            wrapped_labels = [smart_wrap(l, 35) for l in data['Option']]
                            bars = ax.barh(wrapped_labels, data['Value'], color='#4285F4')
                            ax.invert_yaxis()
                            # 彻底解决乱码
                            for t in ax.get_yticklabels(): t.set_fontproperties(prop)
                            for t in ax.get_xticklabels(): t.set_fontproperties(prop)
                            # 解决溢出
                            ax.set_xlim(0, max(data['Value']) * 1.15)
                            for bar in bars:
                                ax.text(bar.get_width(), bar.get_y()+bar.get_height()/2, f" {bar.get_width():.1f}%", va='center', fontproperties=prop)
                        
                        elif ctype == "柱状图":
                            wrapped_labels = [smart_wrap(l, 12) for l in data['Option']]
                            bars = ax.bar(wrapped_labels, data['Value'], color='#34A853')
                            for t in ax.get_xticklabels(): t.set_fontproperties(prop)
                            for t in ax.get_yticklabels(): t.set_fontproperties(prop)
                            ax.set_ylim(0, max(data['Value']) * 1.15)
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
                    st.divider()
                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, "a") as f:
                        for c in charts_for_export:
                            c['buffer'].seek(0)
                            # 导出文件名安全处理
                            safe_name = "".join([x for x in c['title'] if x.isalnum() or x in (' ', '_')])[:25]
                            f.writestr(f"{safe_name}.png", c['buffer'].read())
                    st.download_button("📥 一键下载所有图表", zip_buf.getvalue(), "all_charts.zip")

        except Exception as e:
            st.error(f"运行出错: {e}")

if __name__ == "__main__":
    main()
