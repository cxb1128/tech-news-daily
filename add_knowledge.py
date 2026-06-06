#!/usr/bin/env python3
"""向飞书知识库添加 AI 知识和摄影摄像技巧"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

from feishu_sync import FeishuClient

SPACE_ID = os.environ["FEISHU_SPACE_ID"]

# ── AI & 机器学习 页面内容 ──
AI_CONTENT = """
# 🤖 AI & 机器学习 知识体系

## 一、核心概念速览

### 1.1 机器学习三大范式

- 监督学习 (Supervised Learning): 从标注数据中学习映射关系。分类、回归是典型任务
- 无监督学习 (Unsupervised Learning): 从无标注数据中发现隐藏结构。聚类、降维、异常检测
- 强化学习 (Reinforcement Learning): 智能体在环境中通过试错学习最优策略。AlphaGo、自动驾驶决策

### 1.2 深度学习基石

- 神经网络本质: 多层非线性变换的组合，通过反向传播和梯度下降优化参数
- 激活函数演进: Sigmoid → ReLU → GELU → Swish，核心是解决梯度消失和提升表达力
- 损失函数选择: 交叉熵用于分类，MSE 用于回归，对比损失用于表征学习
- 优化器家族: SGD → Momentum → Adam → AdamW，学习率调度策略至关重要

### 1.3 Transformer 架构理解

- Self-Attention 机制: Q、K、V 三个矩阵，通过点积注意力捕捉序列中任意位置的依赖关系
- Multi-Head Attention: 多个注意力头并行计算，不同头关注不同的语义关系
- Positional Encoding: 为无序的注意力机制注入位置信息，RoPE 已成为主流方案
- 残差连接 + LayerNorm: 稳定深层网络训练，Pre-LN vs Post-LN 影响收敛行为

## 二、大语言模型 (LLM) 深度解析

### 2.1 训练流程三阶段

- Pre-training: 在海量文本上做下一个 token 预测。数据质量 > 数据数量。RedPajama、FineWeb 等开放数据集
- SFT (Supervised Fine-Tuning): 用高质量指令-回复对微调。关键在于数据多样性和回复质量
- RLHF / DPO: 对齐人类偏好。PPO 需要 reward model，DPO 直接从偏好对优化，更简洁稳定

### 2.2 提示工程实战技巧

- Few-shot 思维链: 提供 2-3 个带推理过程的示例，引导模型逐步推理
- 角色设定法: "你是一位资深 XX 专家"，设定领域背景提升回答质量
- 结构化输出: 明确要求 JSON / Markdown 格式，减少解析成本
- 分步指令: 将复杂任务拆解为 "首先...然后...最后..." 的子步骤
- 反面约束: 不仅告诉模型要做什么，也明确不要做什么

### 2.3 RAG (检索增强生成) 架构

- 文档分块策略: 语义分块优于固定大小分块，保留上下文重叠
- Embedding 选型: text-embedding-3-large、bge-large、jina-embeddings-v3
- 向量数据库: Pinecone、Weaviate、Milvus、Qdrant，选型考虑延迟和扩展性
- 检索优化: Hybrid Search (稠密向量 + BM25 稀疏检索) 通常效果最佳
- Re-ranking: 用 Cohere Rerank 或 bge-reranker 二次排序，显著提升召回精度

## 三、AI Agent 设计模式

### 3.1 核心架构

- ReAct 模式: Reasoning + Acting 交替进行，Think → Act → Observe → Think 循环
- Plan-and-Execute: 先制定完整计划，再逐步执行，适合复杂多步任务
- Multi-Agent 协作: 不同 Agent 扮演不同角色（规划者、执行者、评审者），互相检查
- Tool Use / Function Calling: 为 LLM 提供外部工具接口（搜索、计算、代码执行）

### 3.2 Agent 可靠性工程

- 结构化输出约束: JSON Schema / Pydantic 强制输出格式，减少解析失败
- 自检与纠错: 让 Agent 在执行后验证结果，错误时自动重试
- Human-in-the-loop: 关键决策节点设置人工确认，防止不可逆操作
- Token 预算管理: 限制对话轮次和每轮 token 消耗，防止失控循环

## 四、模型评估与选型

### 4.1 评估维度

- 知识与推理: MMLU、GPQA、ARC——衡量知识广度和复杂推理
- 代码能力: HumanEval、SWE-bench——衡量编程和软件工程能力
- 指令遵循: IFEval、MT-Bench——衡量对复杂指令的理解和执行
- 安全对齐: TruthfulQA、Toxigen——衡量事实性和安全性

### 4.2 2025-2026 主流模型速览

- Claude 4.5 Opus: 深度推理最强，适合复杂分析、研究、代码审查
- Claude 4.5 Sonnet: 性能与速度的最佳平衡，通用任务首选
- GPT-5: 多模态能力领先，图像理解和生成集成度高
- Gemini 3.0: 超长上下文 (2M+ tokens)，适合大规模文档分析
- DeepSeek-V4: 开源旗舰，MoE 架构，性价比极高
- Llama 4: Meta 开源，生态丰富，本地部署友好

## 五、学习路线建议

### 5.1 入门阶段 (0→1)
1. 吴恩达 Machine Learning 课程 (Coursera) — 建立直觉
2. fast.ai Practical Deep Learning — 动手训练第一个模型
3. Andrej Karpathy 的 Neural Networks: Zero to Hero (YouTube)

### 5.2 进阶阶段 (1→3)
1. 阅读 Attention Is All You Need 原论文并实现 Transformer
2. 复现 GPT-2 训练 (nanoGPT) — 理解 Scaling Law
3. 学习 Wandb / MLflow 做实验管理
4. 参加 Kaggle 竞赛积累实战经验

### 5.3 精通阶段 (3→5)
1. 深入 CUDA 和 GPU 优化 (Triton, FlashAttention)
2. 多机多卡分布式训练 (FSDP, ZeRO, DeepSpeed)
3. 模型量化和推理优化 (AWQ, GPTQ, vLLM)
4. 从零实现 RLHF/DPO 全流程

## 六、重要论文阅读清单

- "Attention Is All You Need" (2017) — Transformer 起源
- "BERT: Pre-training of Deep Bidirectional Transformers" (2018)
- "GPT-3: Language Models are Few-Shot Learners" (2020)
- "Training language models to follow instructions" (InstructGPT, 2022)
- "Constitutional AI: Harmlessness from AI Feedback" (2022)
- "Direct Preference Optimization" (DPO, 2023)
- "The Llama 3 Herd of Models" (2024)
- "DeepSeek-V3/R1 Technical Report" (2025)

## 七、常用工具与框架

- 训练框架: PyTorch, JAX, HuggingFace Transformers, DeepSpeed
- 推理引擎: vLLM, TensorRT-LLM, Ollama, llama.cpp
- Agent 框架: LangChain, LlamaIndex, CrewAI, AutoGen
- 向量存储: ChromaDB, Pinecone, Milvus, Qdrant
- 实验追踪: Weights & Biases, MLflow, TensorBoard
- 数据标注: Label Studio, Argilla, Prodigy

> 最后更新: 2026年6月 — 保持持续学习，AI 领域的知识半衰期约为 6 个月，定期回顾和更新知识库是必要的习惯。
"""

# ── 摄影摄像技巧 页面内容 ──
PHOTO_CONTENT = """
# 📷 摄影摄像技巧完全指南

## 一、曝光三要素

### 1.1 光圈 (Aperture)
- f/1.4 - f/2.8: 大光圈，浅景深，适合人像、弱光环境。背景虚化明显
- f/5.6 - f/8: 中等光圈，画质最锐，适合大多数场景
- f/11 - f/22: 小光圈，大景深，适合风光、建筑。可能出现衍射现象降低锐度
- 光圈每档进光量差一倍: f/1.4 → f/2 → f/2.8 → f/4 → f/5.6 → f/8 → f/11 → f/16

### 1.2 快门速度 (Shutter Speed)
- 1/8000 - 1/1000: 凝固高速运动 (体育、飞鸟、水滴)
- 1/250 - 1/60: 日常手持拍摄安全范围
- 1/30 - 1": 慢门创意 (流水拉丝、车轨、星轨)
- Bulb 模式: 超长曝光，需要快门线或遥控器
- 安全快门法则: 快门速度 ≥ 1/焦距 (全画幅)，APS-C 需要 ×1.5

### 1.3 ISO (感光度)
- ISO 100-400: 基础感光度，画质最佳，噪点最少
- ISO 800-3200: 暗光手持可行范围，现代相机可接受
- ISO 6400+: 极限暗光，噪点明显但 AI 降噪可挽救
- 原则: ISO 是最后调整的参数，优先用光圈和快门下满足曝光

## 二、构图法则

### 2.1 基础构图
- 三分法 (Rule of Thirds): 将画面九等分，主体放在交点或线条上
- 引导线 (Leading Lines): 利用道路、河流、栏杆等线条引导视线到主体
- 框架构图 (Frame within a Frame): 用门窗、拱廊、树枝框住主体
- 对称构图: 利用水面倒影、建筑对称，营造平衡感
- 负空间 (Negative Space): 大面积留白突出主体，营造意境

### 2.2 进阶构图
- 前景兴趣点: 用前景元素增加画面纵深和层次感
- 色彩对比: 互补色搭配更吸睛 (蓝/橙、红/绿、黄/紫)
- 打破模式: 在重复图案中插入一个不同的元素，制造视觉焦点
- 视角变换: 低角度仰拍强调高大，高角度俯拍展现场景全貌
- 黄金比例: 1:1.618 的螺旋构图，比三分法更自然

### 2.3 人像构图要点
- 头部留白: 头顶上方保留适当空间，避免压迫感
- 视线方向: 人物看向的方向多留空间，增强呼吸感
- 关节裁切: 避免在关节处 (膝盖、手腕、脚踝) 裁切画面
- 景深控制: 眼睛必须清晰，耳朵可以稍微虚化

## 三、光线运用

### 3.1 自然光
- 黄金时刻 (Golden Hour): 日出后和日落前 1 小时，光线温暖柔和，最适合拍摄
- 蓝调时刻 (Blue Hour): 日出前和日落后 30 分钟，天空呈深蓝色调
- 正午强光: 顶光会在眼窝和下巴产生难看的阴影，用反光板或闪光灯补光
- 阴天柔光: 云层是天然柔光箱，适合人像和微距
- 逆光拍摄: 创造轮廓光和发丝光，需要点测光或曝光补偿

### 3.2 人造光
- 三点布光法: 主光 + 补光 + 轮廓光，经典人像布光
- 蝴蝶光 (Butterfly Lighting): 主光在前上方，鼻下产生蝶形阴影
- 伦勃朗光 (Rembrandt Lighting): 主光 45° 侧上方，脸颊形成三角形亮区
- 环形光 (Loop Lighting): 主光稍偏一侧，柔和自然，几乎适合所有人
- 侧光 (Split Lighting): 主光 90° 侧面，一半明亮一半阴影，戏剧性强

### 3.3 闪光灯技巧
- 跳闪: 闪光灯朝天花板或墙壁打光，获得柔和的漫反射光线
- 高速同步 (HSS): 突破快门同步速度限制，大光圈户外补光必备
- 前帘 vs 后帘同步: 运动轨迹在主体前方还是后方的区别
- 离机闪: 闪光灯离开相机，通过引闪器控制，创造立体光影

## 四、相机设置与技巧

### 4.1 拍摄模式选择
- A/Av 光圈优先: 控制景深，适合人像、风光、日常 — 最常用的模式
- S/Tv 快门优先: 控制运动模糊，适合体育、野生动物
- M 手动模式: 完全控制曝光，适合影棚、长曝光、延时摄影
- P 程序自动: 快速抓拍，相机自动选择光圈快门组合

### 4.2 对焦技巧
- 单点对焦 (AF-S): 静态主体，精度最高
- 连续对焦 (AF-C): 运动主体，持续追踪
- 眼部追踪 AF: 人像和动物摄影的利器，锁定眼部
- 后键对焦 (Back Button Focus): 分离对焦和快门，操作更灵活
- 手动对焦辅助: 峰值对焦 + 放大对焦，风光和微距必备

### 4.3 白平衡
- 自动白平衡 (AWB): 大多数场景可靠，但会在暖色调场景中偏冷
- 日光 (~5500K): 标准日光色温
- 阴天 (~6500K): 增加暖色调
- 钨丝灯 (~3200K): 修正室内暖光
- 自定义白平衡: 用灰卡或白卡设置，色彩最准确

## 五、后期处理基础

### 5.1 调色流程
- 第一步: 镜头校正 (畸变、色差、暗角)
- 第二步: 裁剪和水平校正
- 第三步: 基础曝光调整 (曝光、对比度、高光、阴影)
- 第四步: 颜色分级 (色温、色调、饱和度、HSL)
- 第五步: 局部调整 (径向滤镜、渐变滤镜、画笔)
- 第六步: 降噪和锐化 (先降噪后锐化)

### 5.2 常用软件
- Lightroom Classic: 照片管理和 RAW 处理，批量调色效率最高
- Photoshop: 精细修图、合成、创意后期
- Capture One: RAW 解析色彩更出色，联机拍摄首选
- DaVinci Resolve: 免费强大的视频调色软件
- Snapseed (手机): 最佳移动端修图 App

### 5.3 常见风格调色
- 日系清新: 提高曝光 + 降低对比度 + 偏蓝绿色调 + 降低饱和度
- 胶片感: S 曲线 + 提升黑色位 + 三色分离 (阴影偏青/高光偏黄) + 添加颗粒
- 电影感: 16:9 或 2.35:1 画幅 + 青橙色调 (Teal & Orange)
- 黑白: 去除色彩 + 强化对比度 + 局部加深减淡

## 六、视频拍摄基础

### 6.1 基础设置
- 帧率选择: 24fps 电影感 / 30fps 日常视频 / 60fps 流畅运动 / 120fps 慢动作
- 快门速度: 180度快门法则 — 快门 = 1/(2×帧率)，24fps → 1/48s
- 分辨率: 4K 提供后期裁切空间，1080p 文件更小处理更快
- 编码格式: H.264 通用兼容 / H.265 压缩率更高 / ProRes 后期空间大

### 6.2 运镜技巧
- 推拉 (Dolly): 物理移动相机靠近或远离，比变焦更自然
- 横移 (Truck): 相机横向移动，跟随主体或展现场景
- 摇镜 (Pan): 相机在原地旋转，跟随动作或展示全景
- 俯仰 (Tilt): 相机上下旋转，常用于建筑和揭示镜头
- 跟拍 (Tracking): 稳定器跟随主体移动，保持构图一致

### 6.3 稳定技巧
- 三轴稳定器: 手持运镜最常用，学习和调平是关键
- 三脚架: 固定机位、延时摄影、采访
- 手持技巧: 三点支撑 (双手+额头)、忍者步 (屈膝缓行)
- 后期防抖: DaVinci Resolve / Premiere Pro / Final Cut Pro 内置防抖
- 升格慢动作: 60fps+ 拍摄再降速，天然防抖

## 七、设备选购建议

### 7.1 入门推荐
- 预算 5000 以内: 索尼 ZV-E10 II / 佳能 EOS R50 / 富士 X-M5
- 一机一镜原则: 先用套机镜头拍 5000 张照片，再根据自己的需求添置镜头
- 必备配件: 备用电池、SD 卡 (V30 以上)、UV 镜、相机包、气吹清洁套装

### 7.2 进阶升级
- 全画幅入门: 索尼 A7C II / 尼康 Z5 / 佳能 EOS R8
- 第一支定焦: 50mm f/1.8 — "标准镜头"，所见即所得，学习构图最好的焦段
- 人像镜头: 85mm f/1.8 — 压缩感和浅景深兼备
- 风光镜头: 16-35mm f/4 或 f/2.8 — 广角冲击力

### 7.3 手机摄影
- 善用多镜头: 超广角拍建筑风光，长焦拍人像和细节
- 手动/专业模式: 控制曝光和对焦，释放创作自由
- 计算摄影: 夜景模式、HDR、人像模式 — 善用但不依赖
- 手机摄影推荐 App: Halide (iOS)、ProShot (Android)、Blackmagic Cam (视频)

> 摄影的核心不是设备，而是观察力。最好的相机是你随身携带的那台。多拍、多看优秀作品、多思考为什么好——比买任何器材都管用。
"""


def main():
    client = FeishuClient()
    token = client.get_token()
    print(f"✅ 飞书认证成功")

    # ── 1. 更新 AI 页面 ──
    ai_node = "LPSdwYixHivkLKkfmkpc9b8anpl"
    print(f"\n📝 正在更新「AI & 机器学习」页面...")
    try:
        client.update_knowledge_page(ai_node, "🤖 AI & 机器学习 知识体系", AI_CONTENT.strip())
        print("✅ AI 知识页面更新完成！")
    except Exception as e:
        print(f"❌ AI 页面更新失败: {e}")

    # ── 2. 创建摄影技巧页面 ──
    print(f"\n📝 正在创建「摄影摄像技巧」页面...")
    try:
        photo_node = client.create_knowledge_page(
            space_id=SPACE_ID,
            title="📷 摄影摄像技巧完全指南",
            content=PHOTO_CONTENT.strip(),
        )
        print(f"✅ 摄影技巧页面创建完成！node_token: {photo_node}")
    except Exception as e:
        print(f"❌ 摄影页面创建失败: {e}")

    print("\n🎉 知识库内容添加完毕！")


if __name__ == "__main__":
    main()
