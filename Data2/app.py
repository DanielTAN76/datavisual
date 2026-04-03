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
# 请确保你上传到 GitHub 的字体文件名叫 Alibaba.ttf
FONT_FILENAME = 'Alibaba.ttf'  
font_path = os.path.join(current_dir, FONT_FILENAME)

# 初始化字体属性，防止解析元数据崩溃
if os.path.exists(font_path):
    # 直接定位文件路径，不调用 get_name() 避免 FT2Font 报错
    prop = fm.FontProperties(fname=font_path, size=12)
    prop_title = fm.FontProperties(fname=font_path, size=18)
    font_available = True
else:
    st.warning(f"⚠️ 未找到字体文件 {FONT_FILENAME}，将使用系统默认字体（中文可能乱码）。")
    prop = fm.FontProperties(size=12)
    prop_title = fm.FontProperties(size=18)
    font_available = False

# 解决负号显示问题
plt.rcParams['axes.unicode_minus'] = False 

def smart_wrap(text, width):
    """针对中英文混合文本的自动换行逻辑"""
    text = str(text)
    lines = []
    for para in text.split('\n'):
        curr_line, curr_width = '', 0
        for char in para:
            # 判断是否为中文字符
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
    """解析交叉表数据"""
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
                val_str = str(row['col_2']).strip().replace('%', '')
                val = float(val_str)
                curr_opts.append([row['col_1'], val])
            except: pass
    if curr_title and curr_opts:
        questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
    return questions

def main():
    st.set_page_config(page_title="数据可视化工具", layout="wide")
    st.title("📊 交叉表数据可视化")
    
    st.info("💡 请确保已将 Alibaba.ttf 字体文件上传到 GitHub 仓库根目录。")

    uploaded_file = st.file_uploader("第一步：上传您的 Excel 或 CSV 文件", type=["csv", "xlsx", "xls"])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, header=None)
            else:
                df = pd.read_excel(uploaded_file, header=None)
            
            parsed_questions = parse_questions_new(df)

            if not parsed_questions:
                st.error("未能识别出有效题目，请检查文件格式。")
            else:
                st.success(f"成功识别到 {len(parsed_questions)} 个题目")
                
                charts_for_export = []
                
                # 遍历生成的图表
                for i, q in enumerate(parsed_questions):
                    st.divider()
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        st.write(f"**题目 {i+1}:**")
                        st.write(q['title'])
                        ctype = st.selectbox(f"选择类型", ["条形图", "柱状图", "饼图"], key=f"sel_{i}")
                    
                    with col2:
                        # --- 修改 1：稍微增加figsize宽度和高度，优化布局 ---
                        fig, ax = plt.subplots(figsize=(11, 7))
                        
                        # 显式应用标题字体
                        ax.set_title(q['title'], fontproperties=prop_title, pad=20)
                        
                        data = q['data']
                        labels = data['Option']
                        values = data['Value']

                        if ctype == "条形图":
                            # --- 修改 2：调整换行宽度以适应新布局 ---
                            wrapped_labels = [smart_wrap(l, 35) for l in labels]
                            bars = ax.barh(wrapped_labels, values, color='#4285F4')
                            ax.invert_yaxis()
                            
                            # --- 核心修改 3：显式应用中文字体到坐标轴刻度标签 ---
                            # 设置y轴刻度标签字体
                            for t in ax.get_yticklabels(): 
                                t.set_fontproperties(prop)
                            
                            # 设置x轴刻度标签字体
                            for t in ax.get_xticklabels(): 
                                t.set_fontproperties(prop)

                            # --- 核心修改 4：处理文本溢出：手动增加 x 轴范围以预留空白空间 ---
                            max_val = max(values) if not values.empty else 100
                            # 预留 15% 的空白空间给最长的条形图和数据标签
                            ax.set_xlim(0, max_val * 1.15) 
                            
                            for bar in bars:
                                ax.text(bar.get_width(), bar.get_y()+bar.get_height()/2, f" {bar.get_width():.1f}%", 
                                        va='center', fontproperties=prop)
                        
                        elif ctype == "柱状图":
                            wrapped_labels = [smart_wrap(l, 12) for l in labels]
                            bars = ax.bar(wrapped_labels, values, color='#34A853')
                            
                            # --- 修改：柱状图也应用坐标轴刻度字体 ---
                            for t in ax.get_xticklabels(): t.set_fontproperties(prop)
                            for t in ax.get_yticklabels(): t.set_fontproperties(prop)
                            
                            for bar in bars:
                                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height(), f"{bar.get_height():.1f}%", 
                                        va='bottom', ha='center', fontproperties=prop)
                        
                        elif ctype == "饼图":
                            wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
                            # 饼图特殊处理：手动设置每一个文本对象的字体
                            plt.setp(texts, fontproperties=prop)
                            plt.setp(autotexts, fontproperties=prop, color='white')

                        # fig.subplots_adjust 可选项：如果tight_layout还是溢出，可以手动调整
                        # fig.subplots_adjust(left=0.2, right=0.85) 

                        plt.tight_layout()
                        
                        # 转为图片显示
                        buf = io.BytesIO()
                        fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
                        st.image(buf)
                        charts_for_export.append({"title": q['title'], "buffer": buf})
                        plt.close(fig)

                # 下载区域
                if charts_for_export:
                    st.divider()
                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, "a") as f:
                        for c in charts_for_export:
                            c['buffer'].seek(0)
                            safe_name = "".join([x for x in c['title'] if x.isalnum() or x in (' ', '_')])[:20]
                            f.writestr(f"{safe_name}.png", c['buffer'].read())
                    
                    st.download_button("📥 一键下载所有图表", zip_buf.getvalue(), "all_charts.zip", "application/zip")

        except Exception as e:
            st.error(f"处理文件时发生错误: {e}")

if __name__ == "__main__":
    main()
