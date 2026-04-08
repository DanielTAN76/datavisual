import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import zipfile
import os
import re

# --- 1. 字体安全加载逻辑 ---
current_dir = os.path.dirname(__file__)
# 请确保你上传到 GitHub 的字体文件名叫 Alibaba.ttf
FONT_FILENAME = 'AlibabaPuHuiTi-3-65-Medium.ttf'  
font_path = os.path.join(current_dir, FONT_FILENAME)

# 初始化字体属性，防止解析元数据崩溃
if os.path.exists(font_path):
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

def smart_wrap(text, width, max_lines=2):
    """
    针对中英文混合文本的自动换行与截断逻辑。
    使用正则分词，确保英文单词按完整的单词换行，不被强行拆断。
    """
    text = str(text)
    lines = []
    for para in text.split('\n'):
        # 将文本拆分为：英文/数字组合、中文字符、其他符号
        tokens = re.findall(r'[a-zA-Z0-9]+|[\u4e00-\u9fff]|.', para)
        curr_line, curr_width = '', 0
        
        for token in tokens:
            # 判断当前 token 宽度（中文占2，其余视长度而定）
            w = 2 if re.match(r'[\u4e00-\u9fff]', token) else len(token)
            
            # 如果当前行加上新 token 超过宽度，且当前行非空，则换行
            if curr_width + w > width and curr_width > 0:
                if curr_line.strip():
                    lines.append(curr_line.strip())
                curr_line = token.lstrip() # 新行不以空格开头
                curr_width = len(curr_line) if not re.match(r'[\u4e00-\u9fff]', token) else (2 if curr_line else 0)
            else:
                curr_line += token
                curr_width += w
                
        if curr_line.strip():
            lines.append(curr_line.strip())
            
    # 超过指定行数则截断并增加 "..."
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
    if len(s) <= 5 and any(c.isdigit() for c in s):
        return True
    return False

def parse_questions_new(df):
    """解析交叉表数据，支持三种不同的数据格式并自动识别"""
    questions = []
    if df.shape[1] < 3:
        for i in range(df.shape[1], 3):
            df[i] = np.nan
            
    df_subset = df.iloc[:, [0, 1, 2]].copy()
    df_subset.columns = ['col_0', 'col_1', 'col_2']
    
    curr_title, curr_opts = None, []
    
    for _, row in df_subset.iterrows():
        c0 = str(row['col_0']).strip() if pd.notna(row['col_0']) else ''
        if c0.lower() == 'nan': c0 = ''
        c1 = str(row['col_1']).strip() if pd.notna(row['col_1']) else ''
        if c1.lower() == 'nan': c1 = ''
        c2 = row['col_2']
        val = try_parse_value(c2)
        
        c0_notna = bool(c0)
        c1_notna = bool(c1)
        
        if not c0_notna and not c1_notna:
            continue
            
        if c0_notna and is_question_number(c0) and c1_notna:
            if curr_title and curr_opts:
                questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
            curr_title = c1
            curr_opts = []
        elif c0_notna and len(c0) <= 2 and c0.isalpha() and c1_notna and val is not None:
            if curr_title:
                curr_opts.append([c1, val])
        elif c0_notna and c1_notna and val is not None:
            if curr_title and curr_opts:
                questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
            curr_title = c0
            curr_opts = [[c1, val]]
        elif not c0_notna and c1_notna and val is not None:
            if curr_title:
                curr_opts.append([c1, val])
        elif c0_notna and not c1_notna and val is None:
             if curr_title and curr_opts:
                 questions.append({"title": curr_title, "data": pd.DataFrame(curr_opts, columns=['Option', 'Value'])})
             curr_title = c0
             curr_opts = []

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
                
                for i, q in enumerate(parsed_questions):
                    st.divider()
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        st.write(f"**题目 {i+1}:**")
                        st.write(q['title'])
                        ctype = st.selectbox(f"选择类型", ["条形图", "柱状图", "饼图"], key=f"sel_{i}")
                    
                    with col2:
                        data = q['data']
                        labels = data['Option']
                        values = data['Value']

                        # --- 核心修改 1：移除条形图的动态高度，强制使用固定 figsize ---
                        fig, ax = plt.subplots(figsize=(12, 8))

                        ax.set_title(q['title'], fontproperties=prop_title, pad=20)

                        if ctype == "条形图":
                            wrapped_labels = [smart_wrap(l, 35, max_lines=2) for l in labels]
                            bars = ax.barh(wrapped_labels, values, color='#4285F4', height=0.5)
                            ax.invert_yaxis()
                            
                            for t in ax.get_yticklabels(): t.set_fontproperties(prop)
                            for t in ax.get_xticklabels(): t.set_fontproperties(prop)

                            max_val = max(values) if not values.empty else 100
                            ax.set_xlim(0, max_val * 1.15) 
                            
                            for bar in bars:
                                ax.text(bar.get_width(), bar.get_y()+bar.get_height()/2, f" {bar.get_width():.1f}%", 
                                        va='center', fontproperties=prop)
                        
                        elif ctype == "柱状图":
                            wrapped_labels = [smart_wrap(l, 12, max_lines=2) for l in labels]
                            bars = ax.bar(wrapped_labels, values, color='#34A853')
                            
                            for t in ax.get_xticklabels(): t.set_fontproperties(prop)
                            for t in ax.get_yticklabels(): t.set_fontproperties(prop)
                            
                            for bar in bars:
                                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height(), f"{bar.get_height():.1f}%", 
                                        va='bottom', ha='center', fontproperties=prop)
                        
                        elif ctype == "饼图":
                            wedges, texts = ax.pie(values, startangle=90, radius=1.0)
                            
                            kw = dict(arrowprops=dict(arrowstyle="-", color="#666666", lw=1.2),
                                      zorder=0, va="center", fontproperties=prop)
                            
                            for idx, p in enumerate(wedges):
                                ang = (p.theta2 - p.theta1) / 2. + p.theta1
                                y = np.sin(np.deg2rad(ang))
                                x = np.cos(np.deg2rad(ang))
                                
                                sign_x = 1 if x >= 0 else -1
                                horizontalalignment = "left" if sign_x == 1 else "right"
                                
                                pct_val = values.iloc[idx] if hasattr(values, 'iloc') else values[idx]
                                opt_name = labels.iloc[idx] if hasattr(labels, 'iloc') else labels[idx]
                                
                                label_text = f"{opt_name}（{pct_val:.1f}%）"
                                wrapped_label = smart_wrap(label_text, 25, max_lines=3)
                                
                                ax.annotate(wrapped_label, 
                                            xy=(x, y), 
                                            xytext=(1.35 * sign_x, 1.35 * y),
                                            horizontalalignment=horizontalalignment, 
                                            **kw)
                            
                            wrapped_legend_labels = [smart_wrap(l, 20, max_lines=2) for l in labels]
                            ax.legend(wedges, wrapped_legend_labels,
                                      loc="upper center", bbox_to_anchor=(0.5, -0.15),
                                      ncol=3, prop=prop, frameon=False)
                            ax.axis('equal') 

                        # 调整内部边距，让内容去适应设定的 12x8 画布
                        plt.tight_layout()
                        
                        buf = io.BytesIO()
                        # --- 核心修改 2：去除 bbox_inches="tight"，这是保证像素绝对一致的关键所在 ---
                        fig.savefig(buf, format="png", dpi=150)
                        st.image(buf)
                        charts_for_export.append({"title": q['title'], "buffer": buf})
                        plt.close(fig)

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
