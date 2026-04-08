import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import zipfile
import os
import re
from matplotlib.ticker import PercentFormatter

# --- 1. 字体安全加载逻辑 ---
current_dir = os.path.dirname(__file__)
# 请确保字体文件在同级目录下
FONT_FILENAME = 'AlibabaPuHuiTi-3-65-Medium.ttf'  
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

# 解决负号显示问题
plt.rcParams['axes.unicode_minus'] = False 

def smart_wrap(text, width, max_lines=2):
    text = str(text)
    lines = []
    for para in text.split('\n'):
        tokens = re.findall(r'[a-zA-Z0-9]+|[\u4e00-\u9fff]|.', para)
        curr_line, curr_width = '', 0
        for token in tokens:
            w = 2 if re.match(r'[\u4e00-\u9fff]', token) else len(token)
            if curr_width + w > width and curr_width > 0:
                if curr_line.strip(): lines.append(curr_line.strip())
                curr_line = token.lstrip() 
                curr_width = len(curr_line) if not re.match(r'[\u4e00-\u9fff]', token) else (2 if curr_line else 0)
            else:
                curr_line += token
                curr_width += w
        if curr_line.strip(): lines.append(curr_line.strip())
            
    if len(lines) > max_lines:
        last_line = lines[max_lines - 1]
        lines[max_lines - 1] = last_line + "..."
        return '\n'.join(lines[:max_lines])
    return '\n'.join(lines)

def try_parse_value(v):
    if pd.isna(v): return None
    s = str(v).strip().replace('%', '').replace(',', '')
    if s == '': return None
    if s.lower() in ['total', 'nan', 'none']: return None
    try:
        return float(s)
    except ValueError:
        return None

def is_question_number(s):
    s = str(s).strip()
    if not s: return False
    if len(s) <= 5 and any(c.isdigit() for c in s): return True
    return False

# --- 缓存数据解析 ---
@st.cache_data(show_spinner=False)
def parse_questions_new(df):
    questions = []
    if df.shape[1] < 3:
        for i in range(df.shape[1], 3): df[i] = np.nan
            
    df_subset = df.iloc[:, [0, 1, 2]].copy()
    df_subset.columns = ['col_0', 'col_1', 'col_2']
    curr_title, curr_opts = None, []
    
    for _, row in df_subset.iterrows():
        c0 = str(row['col_0']).strip() if pd.notna(row['col_0']) else ''
        if c0.lower() == 'nan': c0 = ''
        c1 = str(row['col_1']).strip() if pd.notna(row['col_1']) else ''
        if c1.lower() == 'nan': c1 = ''
        val = try_parse_value(row['col_2'])
        
        c0_notna, c1_notna = bool(c0), bool(c1)
        
        if not c0_notna and not c1_notna: continue
            
        if c0_notna and is_question_number(c0) and c1_notna:
            if curr_title and curr_opts: questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
            curr_title, curr_opts = c1, []
        elif c0_notna and len(c0) <= 2 and c0.isalpha() and c1_notna and val is not None:
            if curr_title: curr_opts.append([c1, val])
        elif c0_notna and c1_notna and val is not None:
            if curr_title and curr_opts: questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
            curr_title, curr_opts = c0, [[c1, val]]
        elif not c0_notna and c1_notna and val is not None:
            if curr_title: curr_opts.append([c1, val])
        elif c0_notna and not c1_notna and val is None:
             if curr_title and curr_opts: questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
             curr_title, curr_opts = c0, []

    if curr_title and curr_opts:
        questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
    return questions

def main():
    st.set_page_config(page_title="数据可视化工具", layout="wide")
    st.title("📊 交叉表数据可视化")
    
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
                charts_for_export = []
                
                for i, q in enumerate(parsed_questions):
                    st.divider()
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        st.write(f"**题目 {i+1}:**")
                        custom_title = st.text_input("📝 修改标题 (按回车生效)：", value=q['title'], key=f"title_{i}")
                        ctype = st.selectbox(f"选择图表类型", ["条形图", "柱状图", "饼图"], key=f"sel_{i}")
                    
                    with col2:
                        data = q['data']
                        labels = data['Option']
                        values = data['Value']

                        # 饼图需要特殊的比例和布局处理
                        if ctype == "饼图":
                            fig, ax = plt.subplots(figsize=(10, 8)) # 稍微调高高度以容纳图例
                        else:
                            dynamic_size = max(10.0, float(len(labels)) * 0.8)
                            fig, ax = plt.subplots(figsize=(dynamic_size, dynamic_size))
                        
                        if ctype == "饼图":
                            # --- 修改1：减小标题间距 ---
                            ax.set_title(custom_title, fontproperties=prop_title, pad=5) 
                        else:
                            ax.set_title(custom_title, fontproperties=prop_title, pad=20)

                        if ctype == "条形图":
                            # --- 修改2：参考图2设计 ---
                            wrapped_labels = [smart_wrap(l, 35, max_lines=2) for l in labels]
                            # 使用更柔和的蓝色
                            bars = ax.barh(wrapped_labels, values, color='#5B9BD5', height=0.6) 
                            ax.invert_yaxis()
                            
                            ax.set_box_aspect(1)
                            
                            # 字体设置
                            for t in ax.get_yticklabels(): t.set_fontproperties(prop)
                            for t in ax.get_xticklabels(): t.set_fontproperties(prop)
                            
                            # X轴设置百分比格式
                            ax.xaxis.set_major_formatter(PercentFormatter(100))
                            
                            # 设置范围，留出显示数值的空间
                            max_val = max(values) if not values.empty else 100
                            ax.set_xlim(0, max_val * 1.1) 
                            
                            # 添加数值标签
                            for bar in bars:
                                ax.text(bar.get_width(), bar.get_y()+bar.get_height()/2, f"{bar.get_width():.1f}%", 
                                        va='center', ha='left', fontproperties=prop, xytext=(5, 0), textcoords='offset points')
                            
                            # --- 核心修改：去掉边框，增加刻度竖线 ---
                            ax.spines['top'].set_visible(False)
                            ax.spines['right'].set_visible(False)
                            ax.spines['bottom'].set_visible(False)
                            # 保留左侧Y轴线
                            ax.spines['left'].set_color('#CCCCCC') 
                            
                            # 添加 X 轴垂直网格线（刻度竖线）
                            ax.grid(True, axis='x', linestyle='-', color='#EEEEEE', zorder=0)
                            # 隐藏 X 轴刻度线本身（只留标签和网格线）
                            ax.tick_params(axis='x', which='both', bottom=False) 
                            ax.tick_params(axis='y', colors='#666666')

                            plt.tight_layout()

                        elif ctype == "柱状图":
                            wrapped_labels = [smart_wrap(l, 12, max_lines=2) for l in labels]
                            bars = ax.bar(wrapped_labels, values, color='#34A853')
                            
                            ax.set_box_aspect(1)
                            
                            for t in ax.get_xticklabels(): t.set_fontproperties(prop)
                            for t in ax.get_yticklabels(): t.set_fontproperties(prop)
                            for bar in bars:
                                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height(), f"{bar.get_height():.1f}%", va='bottom', ha='center', fontproperties=prop)
                            plt.tight_layout()

                        elif ctype == "饼图":
                            # 饼图不使用 tight_layout，使用 subplots_adjust 精确控制
                            
                            wedges, texts = ax.pie(values, startangle=90, radius=1.0, counterclock=False,
                                                   wedgeprops=dict(width=0.6, edgecolor='w')) # 做成甜甜圈图，视觉更现代
                            
                            kw = dict(arrowprops=dict(arrowstyle="-", color="#666666", lw=1.2), zorder=0, va="center", fontproperties=prop)
                            
                            for idx, p in enumerate(wedges):
                                ang = (p.theta2 - p.theta1) / 2. + p.theta1
                                y = np.sin(np.deg2rad(ang))
                                x = np.cos(np.deg2rad(ang))
                                sign_x = 1 if x >= 0 else -1
                                horizontalalignment = "left" if sign_x == 1 else "right"
                                pct_val = values.iloc[idx] if hasattr(values, 'iloc') else values[idx]
                                opt_name = labels.iloc[idx] if hasattr(labels, 'iloc') else labels[idx]
                                # 优化：将百分比放入标签
                                label_text = f"{opt_name}\n（{pct_val:.1f}%）"
                                wrapped_label = smart_wrap(label_text, 20, max_lines=3)
                                # 稍微减小引导线长度
                                ax.annotate(wrapped_label, xy=(x, y), xytext=(1.25 * sign_x, 1.25 * y), horizontalalignment=horizontalalignment, **kw)
                            
                            wrapped_legend_labels = [smart_wrap(l, 20, max_lines=2) for l in labels]
                            # --- 修改1：减小图例与图片间距 ---
                            # bbox_to_anchor 的 y 值调大（例如 0.0 或 -0.05），使图例上移
                            lgd = ax.legend(wedges, wrapped_legend_labels, loc="lower center", 
                                            bbox_to_anchor=(0.5, 0.0), ncol=3, prop=prop, frameon=False)
                            
                            ax.axis('equal') 
                            
                            # --- 修改1：精确调整整体布局空白 ---
                            # 顶部预留给标题，底部紧凑
                            plt.subplots_adjust(left=0.1, right=0.9, top=0.92, bottom=0.08)

                        buf = io.BytesIO()
                        # 饼图已经手动调整了布局，savefig时不需要 bbox_inches='tight'，否则会重新计算空白
                        if ctype == "饼图":
                            fig.savefig(buf, format="png", dpi=150)
                        else:
                            fig.savefig(buf, format="png", dpi=150, bbox_inches='tight')
                            
                        st.image(buf)
                        charts_for_export.append({"title": custom_title, "buffer": buf})
                        plt.close(fig)

                if charts_for_export:
                    st.divider()
                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, "a") as f:
                        for c in charts_for_export:
                            c['buffer'].seek(0)
                            safe_name = "".join([x for x in c['title'] if x.isalnum() or x in (' ', '_')])[:30]
                            if not safe_name.strip(): safe_name = f"chart_{np.random.randint(1000)}"
                            f.writestr(f"{safe_name}.png", c['buffer'].read())
                    
                    st.download_button("📥 一键打包并应用最新标题下载", zip_buf.getvalue(), "all_charts.zip", "application/zip")

        except Exception as e:
            st.error(f"处理文件时发生错误: {e}")

if __name__ == "__main__":
    main()
