import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import zipfile
import os

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
    如果行数超过 max_lines，则在最后一行末尾加上 '...' 并且截断后续文本。
    """
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
    
    # 判断是否超过允许的最大行数
    if len(lines) > max_lines:
        last_line = lines[max_lines - 1]
        # 预留空间加省略号
        if len(last_line) > 1:
            lines[max_lines - 1] = last_line[:-1] + "..."
        else:
            lines[max_lines - 1] = last_line + "..."
        return '\n'.join(lines[:max_lines])
    return '\n'.join(lines)

def try_parse_value(v):
    """尝试将值解析为浮点数，自动处理百分号和逗号，排除无用字符"""
    if pd.isna(v): return None
    s = str(v).strip().replace('%', '').replace(',', '')
    if s == '': return None
    # 过滤掉标题行中可能存在的 'Total' 等干扰字样
    if s.lower() in ['total', 'nan', 'none']: return None
    try:
        return float(s)
    except ValueError:
        return None

def is_question_number(s):
    """辅助判断是否为纯数字或带少量修饰的题号"""
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
                        fig, ax = plt.subplots(figsize=(11, 7))
                        ax.set_title(q['title'], fontproperties=prop_title, pad=20)
                        
                        data = q['data']
                        labels = data['Option']
                        values = data['Value']

                        if ctype == "条形图":
                            # 默认限制为两行
                            wrapped_labels = [smart_wrap(l, 35) for l in labels]
                            bars = ax.barh(wrapped_labels, values, color='#4285F4')
                            ax.invert_yaxis()
                            
                            for t in ax.get_yticklabels(): t.set_fontproperties(prop)
                            for t in ax.get_xticklabels(): t.set_fontproperties(prop)

                            max_val = max(values) if not values.empty else 100
                            ax.set_xlim(0, max_val * 1.15) 
                            
                            for bar in bars:
                                ax.text(bar.get_width(), bar.get_y()+bar.get_height()/2, f" {bar.get_width():.1f}%", 
                                        va='center', fontproperties=prop)
                        
                        elif ctype == "柱状图":
                            # 默认限制为两行
                            wrapped_labels = [smart_wrap(l, 12) for l in labels]
                            bars = ax.bar(wrapped_labels, values, color='#34A853')
                            
                            for t in ax.get_xticklabels(): t.set_fontproperties(prop)
                            for t in ax.get_yticklabels(): t.set_fontproperties(prop)
                            
                            for bar in bars:
                                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height(), f"{bar.get_height():.1f}%", 
                                        va='bottom', ha='center', fontproperties=prop)
                        
                        elif ctype == "饼图":
                            # 绘制基础纯色块饼图，无内部文字
                            wedges, texts = ax.pie(values, startangle=90, radius=1.0)
                            
                            # 定义连接引线的样式
                            kw = dict(arrowprops=dict(arrowstyle="-", color="#666666", lw=1.2),
                                      zorder=0, va="center", fontproperties=prop)
                            
                            for idx, p in enumerate(wedges):
                                ang = (p.theta2 - p.theta1) / 2. + p.theta1
                                y = np.sin(np.deg2rad(ang))
                                x = np.cos(np.deg2rad(ang))
                                
                                # 判断处于圆盘左侧还是右侧
                                sign_x = 1 if x >= 0 else -1
                                horizontalalignment = "left" if sign_x == 1 else "right"
                                
                                pct_val = values.iloc[idx] if hasattr(values, 'iloc') else values[idx]
                                pct_str = f"{pct_val:.1f}%"
                                
                                # 使用 annotate 绘制线段及百分比标记，稍微向外扩展
                                ax.annotate(pct_str, 
                                            xy=(x, y), 
                                            xytext=(1.25 * sign_x, 1.25 * y),
                                            horizontalalignment=horizontalalignment, 
                                            **kw)
                            
                            # 底部增加统一的图例 (Legend)，文字超长同样会被控制在两行
                            wrapped_legend_labels = [smart_wrap(l, 20) for l in labels]
                            ax.legend(wedges, wrapped_legend_labels,
                                      loc="upper center", bbox_to_anchor=(0.5, -0.05),
                                      ncol=3, prop=prop, frameon=False)
                            ax.axis('equal') # 保证饼图为正圆

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
                            safe_name = "".join([x for x in c['title'] if x.isalnum() or x in (' ', '_')])[:20]
                            f.writestr(f"{safe_name}.png", c['buffer'].read())
                    
                    st.download_button("📥 一键下载所有图表", zip_buf.getvalue(), "all_charts.zip", "application/zip")

        except Exception as e:
            st.error(f"处理文件时发生错误: {e}")

if __name__ == "__main__":
    main()
