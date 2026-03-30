
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import textwrap

def smart_wrap(text, width):
    lines = []
    for para in text.split('\n'):
        current_line = ''
        current_width = 0
        for char in para:
            # Heuristic: CJK characters are roughly twice as wide as ASCII
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
    # Use the first three columns, renaming them for clarity
    df_subset = df.iloc[:, [0, 1, 2]].copy()
    df_subset.columns = ['col_0', 'col_1', 'col_2']

    current_question_title = None
    current_question_options = []

    for index, row in df_subset.iterrows():
        q_num = str(row['col_0'])
        q_text = row['col_1']
        
        # Heuristic: A new question starts with a numeric-like value in the first column.
        is_new_question = pd.notna(pd.to_numeric(q_num, errors='coerce'))

        if is_new_question and pd.notna(q_text):
            # If we were processing a previous question, save it first.
            if current_question_title and current_question_options:
                options_df = pd.DataFrame(current_question_options, columns=['Option', 'Value'])
                questions.append({"title": current_question_title, "data": options_df})
            
            # Start the new question
            current_question_title = q_text
            current_question_options = []
        
        # Heuristic: An option row has a non-numeric value in col_0 and some text in col_1
        elif current_question_title and pd.notna(q_text):
            option_label = q_text
            data_value_raw = str(row['col_2'])
            
            try:
                # Clean the data value (e.g., '1%' -> 1.0)
                data_value = float(data_value_raw.strip().replace('%', ''))
                current_question_options.append([option_label, data_value])
            except (ValueError, AttributeError):
                pass # Ignore rows where data conversion fails

    # Add the very last question being processed
    if current_question_title and current_question_options:
        options_df = pd.DataFrame(current_question_options, columns=['Option', 'Value'])
        questions.append({"title": current_question_title, "data": options_df})
        
    return questions

def main():
    st.title("交叉表数据可视化应用")

    st.write("你好！这是一个帮助你将交叉表数据可视化的工具。")
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

            import matplotlib.font_manager as fm
            plt.rcParams['axes.unicode_minus'] = False

            parsed_questions = parse_questions_new(df)

            if not parsed_questions:
                st.warning("无法自动识别出任何问题。")
                st.info("请确保您的文件格式符合预期：第一列为题号，第二列为题目/选项，第三列为数据。")
            else:
                st.success(f"成功识别出 {len(parsed_questions)} 个问题！")
                st.header("2. 数据可视化")

                # --- Font Fix ---
                font_path = '/System/Library/Fonts/STHeiti Medium.ttc'
                prop = fm.FontProperties(fname=font_path)

                for i, question in enumerate(parsed_questions):
                    st.subheader(f"题目: {question['title']}")

                    chart_type = st.selectbox(
                        "选择图表类型",
                        ["条形图", "柱状图", "饼图"],
                        key=f"chart_type_{i}"
                    )

                    plot_df = question['data'].set_index('Option')
                    data_col = 'Value'

                    if plot_df.empty:
                        st.warning("处理后无有效数据可供绘图。")
                        continue

                    fig, ax = plt.subplots(figsize=(10, 6))
                    
                    formatter = FuncFormatter(lambda y, _: f'{y:.0f}%')
                    labels = plot_df.index.astype(str)

                    if chart_type == "条形图":
                        wrapped_labels = [smart_wrap(l, width=40) for l in labels]
                        bars = ax.barh(wrapped_labels, plot_df[data_col])
                        ax.set_xlabel("百分比", fontproperties=prop)
                        ax.xaxis.set_major_formatter(formatter)
                        ax.set_ylabel("", fontproperties=prop)
                        ax.invert_yaxis()
                        for bar in bars:
                            xval = bar.get_width()
                            ax.text(xval, bar.get_y() + bar.get_height()/2.0, f' {xval:.0f}%', va='center', ha='left', fontproperties=prop)
                    
                    elif chart_type == "柱状图":
                        wrapped_labels = [smart_wrap(l, width=15) for l in labels]
                        bars = ax.bar(wrapped_labels, plot_df[data_col])
                        ax.set_ylabel("百分比", fontproperties=prop)
                        ax.yaxis.set_major_formatter(formatter)
                        ax.set_xlabel("", fontproperties=prop)
                        for bar in bars:
                            yval = bar.get_height()
                            ax.text(bar.get_x() + bar.get_width()/2.0, yval, f' {yval:.0f}%', va='bottom', ha='center', fontproperties=prop)

                    elif chart_type == "饼图":
                        wrapped_labels = [smart_wrap(l, width=30) for l in labels]
                        wedges, texts, autotexts = ax.pie(plot_df[data_col], autopct='%1.1f%%', startangle=90, pctdistance=0.85)
                        ax.legend(wedges, wrapped_labels, title="选项", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), prop=prop)
                        plt.setp(autotexts, size=10, weight="bold", fontproperties=prop)
                        ax.axis('equal')

                    ax.set_title(question['title'], fontsize=16, pad=20, fontproperties=prop)
                    
                    # Set font for tick labels
                    for label in ax.get_xticklabels() + ax.get_yticklabels():
                        label.set_fontproperties(prop)

                    plt.tight_layout()
                    st.pyplot(fig)

        except Exception as e:
            st.error(f"处理文件时出错: {e}")



if __name__ == "__main__":
    main()
