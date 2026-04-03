import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.font_manager as fm
import textwrap
import io
import zipfile
import os

# --- 字体配置逻辑 ---
# 获取当前文件所在目录
current_dir = os.path.dirname(__file__)
# 请确保你上传到 GitHub 的字体文件名与下方一致（建议改为简短的名字）
FONT_FILENAME = 'Alibaba.ttf' 
font_path = os.path.join(current_dir, FONT_FILENAME)

# 初始化字体属性变量
if os.path.exists(font_path):
    prop = fm.FontProperties(fname=font_path, size=14)
    prop_title = fm.FontProperties(fname=font_path, size=24)
    # 告诉 Matplotlib 默认使用这个字体
    plt.rcParams['font.sans-serif'] = [prop.get_name()]
else:
    # 如果没找到字体，显示警告但不崩溃
    st.warning(f"未找到字体文件 {FONT_FILENAME}，中文可能显示为方框。请确保字体已上传至 GitHub 仓库。")
    prop = fm.FontProperties(size=14)
    prop_title = fm.FontProperties(size=24)

plt.rcParams['axes.unicode_minus'] = False # 解决负号显示问题

def smart_wrap(text, width):
    lines = []
    for para in str(text).split('\n'):
        current_line = ''
        current_width = 0
        for char in para:
            char_width = 2 if '\u4e00' <= char <= '\u9fff' else 1
            if current_width + char_width > width:
                lines.append(current_line)
                current_line = char
                current_width = char_width
            else:
                current_line += char
                current_width += char_width
        lines.append(current_line)
    return '\n'.join(lines)

def parse_questions_new(df):
    questions = []
    df_subset = df.iloc[:, [0, 1, 2]].copy()
    df_subset.columns = ['col_0', 'col_1', 'col_2']

    current_question_title = None
    current_question_options = []

    for index, row in df_subset.iterrows():
        q_num = str(row['col_0'])
        q_text = row['col_1']
        is_new_question = pd.notna(pd.to_numeric(q_num, errors='coerce'))

        if is_new_question and pd.notna(q_text):
            if current_question_title and current_question_options:
                options_df = pd.DataFrame(current_question_options, columns=['Option', 'Value'])
                questions.append({"title": current_question_title, "data": options_df})
            current_question_title = q_text
            current_question_options = []
        elif current_question_title and pd.notna(q_text):
            option_label = q_text
            data_value_raw = str(row['col_2'])
            try:
                data_value = float(data_value_raw.strip().replace('%', ''))
                current_question_options.append([option_label, data_value])
            except (ValueError, AttributeError):
                pass

    if current_question_title and current_question_options:
        options_df = pd.DataFrame(current_question_options, columns=['Option', 'Value'])
        questions.append({"title": current_question_title, "data": options_df})
    return questions

def main():
    st.title("交叉表数据可视化应用")
    st.write("请上传您的Excel或CSV文件，应用将自动为您识别问题并生成图表。")

    uploaded_file = st.file_uploader("上传你的交叉表文件", type=["csv", "xlsx", "xls"])

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, header=None)
            else:
                df = pd.read_excel(uploaded_file, header=None)
            
            st.write("上传的数据预览：")
            st.dataframe(df.head())

            parsed_questions = parse_questions_new(df)

            if not parsed_questions:
                st.warning("无法自动识别出任何问题。")
            else:
                st.success(f"成功识别出 {len(parsed_questions)} 个问题！")
                
                charts_for_export = []

                for i, question in enumerate(parsed_questions):
                    st.subheader(f"题目: {question['title']}")
                    chart_type = st.selectbox("选择图表类型", ["条形图", "柱状图", "饼图"], key=f"chart_type_{i}")

                    plot_df = question['data'].set_index('Option')
                    if plot_df.empty:
                        continue

                    fig, ax = plt.subplots(figsize=(10, 6))
                    formatter = FuncFormatter(lambda y, _: f'{y:.0f}%')
                    labels = plot_df.index.astype(str)

                    if chart_type == "条形图":
                        wrapped_labels = [smart_wrap(l, width=30) for l in labels]
                        bars = ax.barh(wrapped_labels, plot_df['Value'], color='#4285F4')
                        ax.xaxis.set_major_formatter(formatter)
                        ax.invert_yaxis()
                        for bar in bars:
                            ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2, f' {bar.get_width():.0f}%', va='center', fontproperties=prop)
                    
                    elif chart_type == "柱状图":
                        wrapped_labels = [smart_wrap(l, width=12) for l in labels]
                        bars = ax.bar(wrapped_labels, plot_df['Value'], color='#34A853')
                        ax.yaxis.set_major_formatter(formatter)
                        for bar in bars:
                            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f'{bar.get_height():.0f}%', va='bottom', ha='center', fontproperties=prop)

                    elif chart_type == "饼图":
                        wedges, texts, autotexts = ax.pie(plot_df['Value'], labels=labels, autopct='%1.1f%%', startangle=90)
                        # 为饼图的每个标签设置字体
                        plt.setp(texts, fontproperties=prop)
                        plt.setp(autotexts, fontproperties=prop, color='white')

                    ax.set_title(question['title'], fontproperties=prop_title, pad=20)
                    
                    # 确保坐标轴刻度也使用中文字体
                    for label in ax.get_xticklabels() + ax.get_yticklabels():
                        label.set_fontproperties(prop)

                    plt.tight_layout()
                    
                    # 显示图片
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
                    st.image(buf)
                    charts_for_export.append({"title": question['title'], "chart_type": chart_type, "buffer": buf})
                    plt.close(fig)

                # 导出逻辑...
                if charts_for_export:
                    st.divider()
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                        for chart in charts_for_export:
                            filename = f"{chart['title']}_{chart['chart_type']}.png"
                            chart['buffer'].seek(0)
                            zip_file.writestr(filename, chart['buffer'].read())
                    
                    st.download_button(label="打包下载所有图表", data=zip_buffer.getvalue(), file_name="charts.zip", mime="application/zip")

        except Exception as e:
            st.error(f"发生错误: {e}")

if __name__ == "__main__":
    main()
