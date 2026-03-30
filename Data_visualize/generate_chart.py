
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

# Set Chinese font
plt.rcParams['font.sans-serif'] = ['PingFang HK'] # You might need to change this to a font available on your system
plt.rcParams['axes.unicode_minus'] = False # Fix for minus signs

# Data from the user
data = {
    "投资时长": ["没有投资过", "不到1年", "1-2年", "3-5年", "6-10年", "10年以上"],
    "比例": [1, 8, 15, 24, 16, 35]
}

df = pd.DataFrame(data)

# Sort the data for better visualization
df["投资时长"] = pd.Categorical(df["投资时长"], ["没有投资过", "不到1年", "1-2年", "3-5年", "6-10年", "10年以上"])
df = df.sort_values("投资时长")

# Create the bar chart
plt.figure(figsize=(10, 6))
sns.barplot(x="投资时长", y="比例", data=df, color="blue")

# Add labels and title
plt.xlabel("投资时长")
plt.ylabel("比例 (%)")
plt.title("投资时长分布")

# Add percentage labels on top of each bar
for index, row in df.iterrows():
    plt.text(row.name, row.比例 + 0.5, f"{row.比例}%", color='black', ha="center")

plt.ylim(0, max(df["比例"]) + 5) # Adjust y-axis limit for better label visibility
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()

# Save the chart
chart_path = "/Users/admin/Documents/trae_projects/Data_visualize/investment_duration_chart.png"
plt.savefig(chart_path)
print(f"柱状图已保存到: {chart_path}")
