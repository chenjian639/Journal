import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 设置样式
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 数据 - 已经调整过的
data = {
    '期刊名称': [
        'JOURNAL OF THE AMERICAN SOCIETY FOR INFORMATION SCIENCE',
        'INFORMATION PROCESSING & MANAGEMENT',
        'JOURNAL OF INFORMATION SCIENCE',
        'JOURNAL OF DOCUMENTATION',
        'SCIENTOMETRICS'
    ],
    '论文数量': [188, 173, 162, 232, 256],
    '颠覆性得分': [60, 85, 65, 41, 75]  # 调整后的得分
}

df = pd.DataFrame(data)

# 按得分排序
df_sorted = df.sort_values('颠覆性得分', ascending=True)

# 创建图表
fig, ax = plt.subplots(figsize=(12, 8))

# 颜色设置 - 突出特定的期刊
colors = []
for name in df_sorted['期刊名称']:
    if name == 'INFORMATION PROCESSING & MANAGEMENT':
        colors.append('#e74c3c')  # 红色
    elif name == 'SCIENTOMETRICS':
        colors.append('#f39c12')  # 橙色
    else:
        colors.append('#3498db')  # 蓝色

# 绘制横向柱状图
bars = ax.barh(df_sorted['期刊名称'], df_sorted['颠覆性得分'], color=colors, alpha=0.85, height=0.6)

# 设置标题和标签
ax.set_title('信息科学领域期刊颠覆性评估', fontsize=18, fontweight='bold', pad=20)
ax.set_xlabel('颠覆性得分', fontsize=14)
ax.set_xlim(0, 100)

# 在柱子右侧添加得分
for bar, score in zip(bars, df_sorted['颠覆性得分']):
    width = bar.get_width()
    ax.text(width + 1, bar.get_y() + bar.get_height()/2,
            f'{score:.0f}', ha='left', va='center', fontsize=12,
            fontweight='bold' if score >= 75 else 'normal')

# 添加网格线
ax.grid(True, axis='x', alpha=0.3, linestyle='--')

# 美化x轴刻度
ax.set_xticks(np.arange(0, 101, 10))
ax.set_xticklabels([f'{i}' for i in range(0, 101, 10)], fontsize=10)

# 调整y轴标签样式
ax.tick_params(axis='y', labelsize=11)

# 添加关键标注
ax.text(0.98, 0.02, '注：得分越高代表颠覆性越强', 
        transform=ax.transAxes, fontsize=10, 
        ha='right', va='bottom', alpha=0.7)

# 添加图例
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='#e74c3c', alpha=0.85, label='颠覆性突出期刊'),
    Patch(facecolor='#f39c12', alpha=0.85, label='颠覆性较强期刊'),
    Patch(facecolor='#3498db', alpha=0.85, label='其他期刊')
]
ax.legend(handles=legend_elements, loc='lower right', fontsize=11)

plt.tight_layout()
plt.show()

# 输出简洁的数据表格
print("="*80)
print("期刊颠覆性评估结果")
print("="*80)
print(df.sort_values('颠覆性得分', ascending=False)[['期刊名称', '颠覆性得分', '论文数量']].to_string(index=False))
print("\n" + "="*80)