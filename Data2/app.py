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
FONT_FILENAME = 'AlibabaPuHuiTi-3-65-Medium.ttf'  
font_path = os.path.join(current_dir, FONT_FILENAME)

prop = fm.FontProperties(size=12)
prop_title = fm.FontProperties(size=18)

if os.path.exists(font_path):
    try:
        prop = fm.FontProperties(fname=font_path, size=12)
        prop_title = fm.FontProperties(fname=font_path, size=18)
    except:
        st.error("字体文件加载异常，请检查 Alibaba.ttf 是否完整。")

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

# --- 核心：全自动智能解析器 ---
def smart_parse_data(df):
    questions = []
    curr_title = None
    curr_opts = []

    # 预处理：删除全空行
    df = df.dropna(how='all').reset_index(drop=True)

    for i, row in df.iterrows():
        # 读取前三列，转换为字符串并去空格
        s0 = str(row[0]).strip() if pd.notna(row[0]) else ""
        s1 = str(row[1]).strip() if pd.notna(row[1]) else ""
        s2 = str(row[2]).strip() if pd.notna(row[2]) else ""

        # 尝试解析第三列数值
        val = None
        try:
            val = float(s2.replace('%', '').strip())
        except:
            pass

        # --- 判定逻辑：是否是新题目开始 ---
        is_new_q = False
        detected_title = ""
        first_opt = None

        if s0 != "":
            # A列不为空。我们要区分它是“题号”还是“题目文本”。
            # 规则1：如果A列很短（<=5位）且B列不为空，通常A是题号，B是题目
            if len(s0) <= 6 and s1 != "" and val is None:
                is_new_q = True
                detected_title = s1
            # 规则2：如果A列内容较长，通常A直接就是题目（如 HK客群文件）
            elif len(s0) > 1:
                is_new_q = True
                detected_title = s0
                # 如果这一行 B、C 列已经有数据了，说明题目和第一项在同一行
                if s1 != "" and val is not None:
                    first_opt = [s1, val]

        # 如果判定为新题，保存旧题，开启新题
        if is_new_q:
            if curr_title and curr_opts:
                questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
            curr_title = detected_title
            curr_opts = []
            if first_opt:
                curr_opts.append(first_opt)
        else:
            # 如果不是新题，且当前已经有题目在处理中，则视为添加选项
            if curr_title and s1 != "" and val is not None:
                # 排除掉一些干扰项（如选项也叫“Total”等）
                if s1.lower() not in ['total', '合计', 'nan']:
                    curr_opts.append([s1, val])

    # 保存最后一题
    if curr_title and curr_opts:
        questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
    
    return questions

def main():
    st.set_page_config(page_title="全自动数据可视化", layout="wide")
    st.title("📊 智能数据分析工具")
    st.caption("支持格式：A列题号+B列题目 或 A列直接为题目文本")

    uploaded_file = st.file_uploader("上传您的 Excel 或 CSV 文件", type=["csv", "xlsx", "xls"])

    if uploaded_file:
        try:
            # 读取数据
            if uploaded_file.name.endswith('.csv'):
                # 尝试多种编码防止乱码
                try:
                    df = pd.read_csv(uploaded_file, header=None, encoding='utf-8')
                except:
                    df = pd.read_csv(uploaded_file, header=None, encoding='gbk')
            else:
                df = pd.read_excel(uploaded_file, header=None)
            
            # 执行智能解析
            with st.spinner('正在分析数据布局...'):
                parsed_questions = smart_parse_data(df)

            if not parsed_questions:
                st.error("未能识别出题目内容。请检查文件第一列是否包含题号或题目。")
                with st.expander("查看原始数据预览"):
                    st.write(df.head(10))
            else:
                st.success(f"🤖 自动识别成功：共找到 {len(parsed_questions)} 个有效题目")
                
                charts_for_export = []
                for i, q in enumerate(parsed_questions):
                    st.divider()
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        st.write(f"**Q{i+1}:** {q['title']}")
                        ctype = st.selectbox(f"图表类型", ["条形图", "柱状图", "饼图"], key=f"c_{i}")
                    
                    with c2:
                        fig, ax = plt.subplots(figsize=(11, 7))
                        ax.set_title(q['title'], fontproperties=prop_title, pad=25)
                        
                        data = q['data']
                        if ctype == "条形图":
                            labels = [smart_wrap(l, 30) for l in data['Option']]
                            bars = ax.barh(labels, data['Value'], color='#4285F4')
                            ax.invert_yaxis()
                            for t in ax.get_yticklabels() + ax.get_xticklabels(): t.set_fontproperties(prop)
                            ax.set_xlim(0, max(data['Value']) * 1.15 if not data['Value'].empty else 100)
                            for bar in bars:
                                ax.text(bar.get_width(), bar.get_y()+bar.get_height()/2, f" {bar.get_width():.1f}%", va='center', fontproperties=prop)
                        
                        elif ctype == "柱状图":
                            labels = [smart_wrap(l, 12) for l in data['Option']]
                            bars = ax.bar(labels, data['Value'], color='#34A853')
                            for t in ax.get_xticklabels() + ax.get_yticklabels(): t.set_fontproperties(prop)
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
                            safe_name = "".join([x for x in c['title'] if x.isalnum() or x in (' ', '_')])[:25]
                            f.writestr(f"{safe_name}.png", c['buffer'].read())
                    st.download_button("📥 打包下载所有图表", zip_buf.getvalue(), "all_charts.zip")

        except Exception as e:
            st.error(f"解析过程中发生错误: {e}")

if __name__ == "__main__":
    main()
