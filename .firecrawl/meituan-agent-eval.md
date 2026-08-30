[![美团 · 技术团队](https://p0.meituan.net/meituantechblog/00c62e57b4c4a1f40b47d7152b3e54b511963.png)美团 · 技术团队](https://tech.meituan.com/)

[首页](https://tech.meituan.com/)

[历史文章](https://tech.meituan.com/history.html)

[技术沙龙](https://tech.meituan.com/tech-salon.html)

[关于我们](https://tech.meituan.com/about.html)

![Agent评测漫谈 —— 由浅入深讲解Agent评测](https://p1.meituan.net/meituantechblog/07ca6e0dbead38c588608aba7b687169493204.jpg)

# Agent评测漫谈 —— 由浅入深讲解Agent评测

履约技术团队 2026-08-07 1

Agent大模型

本篇博客是一篇科普文章，由浅入深的介绍Agent评测。其中前两章系统介绍了评测是什么，以及如何建立评测体系；其中第二章是美团图灵Agent评测团队深入美团各业务团队BP总结出的实践经验，是我们在两年实践过程中逐步打磨出来的认知。第三章重点介绍了龙虾/爱马仕这类长程Agent框架的出现对评测带来的变化。

本篇博客在美团内部发表之后获得了较多的关注，我们发现大家对Agent评测的热情非常高，因此我们决定将内部博客进行公开，想把这些经验分享给更多的同学，希望对大家有所启发或帮助。

## [一、Agent评测是什么](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#%E4%B8%80%E3%80%81agent%E8%AF%84%E6%B5%8B%E6%98%AF%E4%BB%80%E4%B9%88)

### [1.1 评测的核心目的](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_1-1-%E8%AF%84%E6%B5%8B%E7%9A%84%E6%A0%B8%E5%BF%83%E7%9B%AE%E7%9A%84)

评测的核心目的是为了回答 **Agent 的好不好？以及到底哪里好，哪里不好？** 从而为下一轮迭代指明方向。评测是Agent效果的“精密量具”。

这也是为什么 Agent 评测不能只停留在离线打榜，更不能只看某次 Demo 的表现。它必须服务于真实业务中的研发、上线、回归、优化和规模化落地。

而Agent评测的基石是观测，因此我们得出了Agent研发公式 —— 观测 + 评测 = 持续迭代

### [1.2 Agent评测与传统模型评测的不同](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_1-2-agent%E8%AF%84%E6%B5%8B%E4%B8%8E%E4%BC%A0%E7%BB%9F%E6%A8%A1%E5%9E%8B%E8%AF%84%E6%B5%8B%E7%9A%84%E4%B8%8D%E5%90%8C)

评测方法会随着 AI 形态变化而变化，大致经历了三个阶段：

![](https://p0.meituan.net/meituantechblog/5a8954c2e7b681ee8fb8d2c8a73868cd157865.png)

传统机器学习更像在回答“算得准不准”。 大模型评测开始回答“模型能力强不强”。 而 Agent 评测真正要回答的是：

> 当模型被放进一个真实系统里，和 Prompt、Skill、工具链、记忆、状态管理、业务流程耦合在一起后，它能不能稳定交付好的结果。

这意味着 Agent 的评测对象已经不再是单一模型，而是一个“模型 + 系统 + 工具 + 流程”的复杂系统。

### [1.3 为什么Agent评测不是只看结果，还要看行为和过程](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_1-3-%E4%B8%BA%E4%BB%80%E4%B9%88agent%E8%AF%84%E6%B5%8B%E4%B8%8D%E6%98%AF%E5%8F%AA%E7%9C%8B%E7%BB%93%E6%9E%9C-%E8%BF%98%E8%A6%81%E7%9C%8B%E8%A1%8C%E4%B8%BA%E5%92%8C%E8%BF%87%E7%A8%8B)

在真实场景中，两个 Agent 可能最终都“做对了”，但工程价值完全不同：

- 一个路径清晰、工具调用稳定、耗时可控、可重复复现
- 一个反复试错、路径混乱、靠偶然命中结果、不可复现

如果只看最终答案，这两者会被误判为同一水平；但从规模化、成本优化、用户体验的角度看，差别非常大。

因此，Agent 评测至少需要覆盖四层内容：

- **结果层**：任务是否完成，输出是否可用
- **过程层**：规划是否合理，步骤是否稳定
- **效率层**：耗时、Token、工具调用次数是否可接受
- **风险层（安全层）**：是否越权、是否误操作、是否存在安全隐患

从这个意义上讲，自2023年GPT爆火以来，Agent发展从ChatBot形态快速发展至ClaudCode、OpenClaw这样的多功能长程Agent，Agent能力日渐强大，Agent评测正在从“答案评测”走向“行为评测”。

### [1.4 为什么说观测是评测的基石](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_1-4-%E4%B8%BA%E4%BB%80%E4%B9%88%E8%AF%B4%E8%A7%82%E6%B5%8B%E6%98%AF%E8%AF%84%E6%B5%8B%E7%9A%84%E5%9F%BA%E7%9F%B3)

有一个朴素的认知：Agent 属于广义的 SaaS 层，大模型赋予Agent泛化能力但也带出随机性的问题，而用户仍旧期望得到一个稳定可靠的智能体。为了弥合“随机性”与“可靠性”之间的鸿沟，我们必须回归工程视角看待Agent —— **看不见的问题，几乎不可能被稳定解决**。

Agent 的一次执行通常包含如下链路：

![](https://p0.meituan.net/meituantechblog/6a9ba42edcd2f8bd0ec7d23d4983147a257714.png)

只要其中任意一层出问题，最终效果都可能劣化。为了结果稳定，我们需要过程稳定。但如果日志系统只能看到“用户说了什么”和“最后回复了什么”，就几乎无法判断问题根因。正是基于“ **我想看Case却发现没打日志**”这个朴素的问题，工业界发展出了 Trace 系统，将黑盒内部的逻辑推理过程进行全路径的披露，将所有影响模型输出的输入信息都记录下来。

对 Agent 的每一个“隐形动作”进行精准观测，是实现从“概率性生成”向“工业级可靠性”跨越的必由之路。

### [1.5 小结：Trajectory Evaluation 与 Response Evaluation](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_1-5-%E5%B0%8F%E7%BB%93-trajectory-evaluation-%E4%B8%8E-response-evaluation)

经过前文的论述，我们知道Agent评测本质是在回答好不好，为迭代指明方向。而Agent评测本身既要关注结果（Response）也要关注过程（Trace或者叫做Trajectory）。

## [二、评测的核心方法论](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#%E4%BA%8C%E3%80%81%E8%AF%84%E6%B5%8B%E7%9A%84%E6%A0%B8%E5%BF%83%E6%96%B9%E6%B3%95%E8%AE%BA)

### [2.1 评测体系的核心不是堆指标，而是搭桥](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_2-1-%E8%AF%84%E6%B5%8B%E4%BD%93%E7%B3%BB%E7%9A%84%E6%A0%B8%E5%BF%83%E4%B8%8D%E6%98%AF%E5%A0%86%E6%8C%87%E6%A0%87-%E8%80%8C%E6%98%AF%E6%90%AD%E6%A1%A5)

有的同学会好奇，为什么一定要“搭桥”？这是因为Agent评测体系必须追求业务价值与评测指标之间的解释性。而Agent 评测的难点之一，是模型能力指标和业务结果指标之间有天然鸿沟。

![](https://p0.meituan.net/meituantechblog/0791bdb6ec11d84dfcc4a4b667164383100037.png)

这两类指标不能直接映射，中间必须有一层面向任务系统的桥梁指标。我们提供一种分层思路如下：

![](https://p0.meituan.net/meituantechblog/fa88ffeb3556e0e8d6b2f12e8e2dbf6b146404.png)

以 AI 搜索为例，业务可能关心DAU、留存和点击；搜索系统本身关心召回率和点击率；Agent 层则关心意图识别是否准确、检索是否有效、结果整合是否可信。

只有把这些层次串起来，才能真正回答“为什么业务指标变差”以及“模型能力提升为什么没有带来业务收益”。这件事必须依赖真正懂业务流程的人来共同建立指标体系。

### [2.2 客观评测与主观评测并行](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_2-2-%E5%AE%A2%E8%A7%82%E8%AF%84%E6%B5%8B%E4%B8%8E%E4%B8%BB%E8%A7%82%E8%AF%84%E6%B5%8B%E5%B9%B6%E8%A1%8C)

经过第一章的介绍，我们知道，Agent的核心目标就是要稳定地交付好的结果。行业内 Agent 评测大量借鉴了大模型评测的方法论，总体上可以拆成客观评测和主观评测：

![](https://p0.meituan.net/meituantechblog/728970da126530ee8541775cac60508c277172.png)

因此更现实的做法通常是：

- 用客观评测覆盖高频、结构化、可规则化的部分
- 用主观评测覆盖开放性、高价值、复杂业务场景
- 用主观评测校准客观评测和 AI 评测，再把规模化部分交给自动化系统

### [2.3 使用“人人一致、人机一致”的方法论对齐主观评测](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_2-3-%E4%BD%BF%E7%94%A8-%E4%BA%BA%E4%BA%BA%E4%B8%80%E8%87%B4%E3%80%81%E4%BA%BA%E6%9C%BA%E4%B8%80%E8%87%B4-%E7%9A%84%E6%96%B9%E6%B3%95%E8%AE%BA%E5%AF%B9%E9%BD%90%E4%B8%BB%E8%A7%82%E8%AF%84%E6%B5%8B)

“好不好”是一个主观问题，主观的标准需要对齐，否则我们不能确定某次迭代之后，到底是指标的抖动带来的提升还是真实的效果提升。

在评测实践中，真正困难的不是“没有人会评”，而是“不同的人评得不一样，机器和人评得也不一样”。在过去一年，我们图灵团队深度BP业务方的过程中，我们发现多个团队相继踩入了相同的坑。

图灵评测积累的关键认知可以概括为“人人对齐和人机对齐”，具体如下：

- **人人一致**：1个“独裁者”好过10个“民主者”。需要一位强有力的角色，拉齐产品、运营、研发、QA的评测标准，遵循同一套评测体系，避免大家各自为政。不同评测员通过背靠背标注的方法拉齐标准。

![](https://p0.meituan.net/meituantechblog/c8424009679d2ecc1b00466290ebc522589569.png)

- **人机一致**：机器评测结果与人工评测结果保持一致，否则不置信。人机一致的意义在于规模化提效，以应对更大的业务流量。

具体如何进行对齐呢？最佳实践是把模糊指标下钻成更细的评测Rubric（或者叫评测维度：学界关于评测维度dimension和评测规则rubric的说法尚未统一，我们这里与开源项目Arize AI对齐），再把每个Rubric尽可能二元化。具体如下：

- **指标下钻**：把“大而模糊”的概念下钻拆解成多个清晰维度
- **Rubric 二元化**：把打分规则尽量收敛成是/否/未知、0/1/unknown
- **持续迭代**：用 unknown 占比来反查 Rubric 是否定义合理，直到单条 Rubric 的人人一致率、人机一致率达到可信阈值（例如85%、90%）

这种拆解法的价值在于：从“主观的模糊感受”转向“可判断的事实依据”，用下钻降低模糊度，从而降低人与人之间、人与机器之间的分歧。应用这套方法，数字站长的人机一致率可以达到99%。Beam以图灵的二元化方案改造评测体系，人机一致率从62%提升到92%。

下面我们分享两个案例。

案例一：如何评价初中生作文的好坏？（满分40分）

![](https://p0.meituan.net/meituantechblog/bcd654d41d8dc247cafa5648750234fc123958.png)

案例二：以骑手外呼场景模型回复是否“口语化”举例

经典错误示范 —— 请判断大模型的回答是否口语化，并按照0到10分打分。

下钻与二元化之后的改进版：

- 模型是否以您指代骑手；
- 模型是否使用“甭客气”，“明儿见”等非官方文书的口语交流词汇；
- 模型输出是否包含“吧”，“呢”，“那个”等语气词汇。

补充：标注和评测的关系是什么？

其中，标注是一种动作，而评测是一套目标导向的判断流程。机器预标注可以帮助人工提效，但只有在人机一致率保障才能称为自动化评测，否则只是机器标注。

### [2.4 Agent评测是一门实践科学](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_2-4-agent%E8%AF%84%E6%B5%8B%E6%98%AF%E4%B8%80%E9%97%A8%E5%AE%9E%E8%B7%B5%E7%A7%91%E5%AD%A6)

从执行链路看，Agent 评测可以被拆成五个关键环节，

- **采集**：采集线上或沙箱中的原始任务数据
- **清洗**：去重、归类、补上下文、修复脏数据
- **评测**：人工评测、AI 评测
- **质检**：检查评测标准是否稳定、评测结果是否可信
- **分析/归因**：定位问题归因，形成优化建议和回归任务

这5个环节与线上AB、持续观测共同构成了Agent迭代的数据飞轮。

绝大部分新上手Agent评测团队都有一个误区 —— 多方调研总结设计一个复杂精妙的评测指标体系，而越复杂的指标越难以执行和对齐。

而Agent评测是一门实践科学。 **起步阶段“让数据飞轮高效运转起来”的意义远大于“设计一个复杂精妙的评测体系”。评测体系的建立不是一蹴而就的，而是依靠 Good Case 和 Bad Case 喂养的**。

因此 ，Agent 评测指标体系的搭建最佳实践路径如下：

- 从高频核心场景起步，先定义少量关键指标
- 从生产环境中收集 Bad Case
- 沉淀高质量 Good Case，明确什么叫“好”
- 把 Good/Bad Case 转成标准评测样本
- 用评测结果反哺 Prompt、Skill、策略和模型优化等等
- 再从新的线上表现里持续抽样，形成下一轮迭代

其中，Bad Case 的价值往往更高，因为它最容易暴露能力边界和系统短板；而 Good Case 的作用则是帮助团队定义高质量完成的范式。

一个成熟的评测团队，核心能力不是一开始就搭出完美系统，而是能把线上问题、失败样本、模糊反馈不断转化成结构化评测资产。我们通过Bad Case和Good Case修正评测体系的目标，逐步修正“独裁者”与真实目标之间的负面偏差。例如履约数字站长业务，项目启动之处只有20多个评测指标，而经历1年时间推全之后，我们扩展到了近200个指标。

### [2.5 专家知识补充模型能力在垂域场景的不足](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_2-5-%E4%B8%93%E5%AE%B6%E7%9F%A5%E8%AF%86%E8%A1%A5%E5%85%85%E6%A8%A1%E5%9E%8B%E8%83%BD%E5%8A%9B%E5%9C%A8%E5%9E%82%E5%9F%9F%E5%9C%BA%E6%99%AF%E7%9A%84%E4%B8%8D%E8%B6%B3)

从GPT 3.5发布至今，虽然基座能力发生了天翻地覆的变化，但是模型能力终究不是万能的。在过去三年的Agent实践中，我们遇到过大量脱离实际的“许愿式”需求。我们要知道模型是训练出来的，模型本身拟合了Token的概率分布，即便在大规模参数下会产生能力的“涌现”，但模型能力的提升依旧强依赖语料的输入，尤其是高质量语料的输入。无论是早期的RLHF，还是如今的DPO、GRPO等算法，虽然训练架构在不断简化，但对高质量核心数据的依赖从未改变。

例如字节专门设立了众包专家标注平台 Xpert，用于生产地理、代码、法律、医学等专业领域的高质量数据，以此支撑豆包基座模型的迭代训练。基座模型能力的提升，大家的直观感受就是它在一个又一个垂直领域的表现越来越好。

因此，当我们在特定垂域面临业务知识语料匮乏（或公网无公开高质数据）的挑战时，通过引入行业专家的知识输入来补足模型/Agent的能力，就成了破局的关键——尤其是在项目的冷启动阶段。

![](https://p0.meituan.net/meituantechblog/38f14cf00310f5e510a565afe5add85475210.png)

呼应前文，评测的目的是回答“Agent好不好”，那么谁来定义“好不好”呢？靠最懂业务最有Sense的行业专家。

### [2.6 小结&FAQ](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_2-6-%E5%B0%8F%E7%BB%93-faq)

这个章节讲述的是图灵评测从履约的项目出发，又经过这1年多BP公司各个业务方的过程中沉淀的核心方法论。

**FAQ**

**Q1：“独裁者”必须是1个人吗，还是1个团队共同遵循一套评测规范即可？**

首先一个团队需要遵循同一套评测体系。独裁者的作用多方征求意见并整合评测体系，当项目方观念无法对齐的时候，由独裁者拍板定论，避免评测体系分化带来项目方各自为政以及内部拉扯带来的损耗。

**Q2：评测体系依赖“独裁者”，存不存在风险？**

我们要认清一个事实，评测体系是不断演进的。从业务冷启动到扩量再到全量，这个过程中用户从愿意尝鲜的AI爱好者扩展到全部用户，用户画像会发生明显的偏移。这导致评测目标需要随着业务的扩量不断地发生调整。独裁者的价值更多的体现在拉齐标准，评测目标更多的是由真实的业务场景中BadCase/Good Case修正并驱动的。当然，我们需要在评测标准建立之初选出最懂业务的人来制定评测体系。

**Q3：冷启动阶段一定要设立种子评测集吗？能不能直接小流量开灰上线，直接收集Good Case和Bad Case来驱动评测呢？**

冷启动阶段是否必须设立种子评测集，本质上是一个风险与成本的Trade-Off。

为什么建议设立种子集：大模型具有随机性，Corner Case 可能会导致Agent体验剧烈偏移。因此，需要通过回测保证Agent基线能力，不断融入Good Case和Bad Case来拓宽Agent的能力边界。

关于小流量开灰的策略：如果业务场景容错率高，或者构建高质量种子集的成本远超线上试错带来的负面反馈，可以尝试小流量上线收集线上case。

**推荐落地方案**：人工生产少量评测集后，AI辅助生成或扩写，以较低成本完成冷启动的种子评测集构建。

**Q4：我们邀请的行业专家对“好”的定义不一致应该怎么办？**

**答**：最朴素且有效的方法，邀请一批行业专家定义“好”的标准，从中抽取共性的部分建设评测体系。例如邀请金牌销售来定义优秀的销售SOP。

那么非共性的部分就没有价值了吗？并非如此。对于专家意见不一致的部分，往往意味着业务本身存在多种优秀策略。我们可以将这些分歧转化为 Agent 的不同风格或策略分支（例如：AI电销中，老练激进派 vs 细水长流派），并允许在不同的测试集（Benchmark）中独立评测。这些分歧点非但不是噪声，反而会成为 Agent 未来走向精细化迭代、覆盖更多长尾场景的重要养分。

## [三、Agent观测评测的演进](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#%E4%B8%89%E3%80%81agent%E8%A7%82%E6%B5%8B%E8%AF%84%E6%B5%8B%E7%9A%84%E6%BC%94%E8%BF%9B)

2023年GPT爆火，2024年工作流出现，去年 Claude Code发布，再到今年的龙虾热、爱马仕热，长程Agent逐渐进入了大众视野。Agent Harness也全面进入长程Agent时代。

长程Agent（Long-horizon Agent）与短程Agent的区别，在于它如何处理“时间跨度带来的复杂性”：

![](https://p0.meituan.net/meituantechblog/8f8ece9a28d04ecfddfb2adeda215de5422438.png)

这些差异会为观测评测带来怎样的变化呢？

### [3.1 短程Agent时代的观测评测](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_3-1-%E7%9F%AD%E7%A8%8Bagent%E6%97%B6%E4%BB%A3%E7%9A%84%E8%A7%82%E6%B5%8B%E8%AF%84%E6%B5%8B)

短程Agent时代的评测对象相对简单。ChatAgent 时代的典型输入输出形态是：`Query -> Answer`。

这类场景的共同特点是：Agent 更多是在“回答问题”，进行少量的系统操作，而不是“进入操作系统执行任务”。典型应用场景，例如AI搜索、客服机器人。此类Agent评测重点通常落在回答本身，例如：

![](https://p0.meituan.net/meituantechblog/9f0173186662a5fc1f713ea812e1bedf123607.png)

在过去1年的发展中图灵形成了成熟的解决方案，包括人工评测、机器评测，部分案例如下：

![](https://p1.meituan.net/meituantechblog/ed3a1d605c114a237925bb77f1d3b4f1531735.png)

### [3.2 长程Agent的观测评测](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#_3-2-%E9%95%BF%E7%A8%8Bagent%E7%9A%84%E8%A7%82%E6%B5%8B%E8%AF%84%E6%B5%8B)

**3.2.1 长程Agent带来评测范式变化**

长程 Agent 解决的不是“回答一个问题”，而是“完成一个复杂任务”。它通常需要：

- 任务需要多步骤拆解
- 执行过程中需要多次调用 Tool 或 Skill
- 需要读取中间结果并动态调整策略

让我们回顾一下观测和评测的目标，带着这个目标去看长程Agent

- **观测目标**：还原现场，精确定位，解决“我想看Case却发现没打日志”的问题
- **评测目标**：回答Agent好不好，指出迭代方向

![](https://p0.meituan.net/meituantechblog/ded0f067e5f7efd742b99b90aa39d751334664.png)

**3.2.2 Skill评测**

在讲Skill评测之前，我们先分享一下我们关于26年春节后这一轮龙虾/Skill热潮的调研。

谁在提出龙虾和Skill的评测需求（2月至今龙虾/Skill热潮的用户画像）？

总结起来目前龙虾和Skill相关需求主要 广义的运营提效 场景，大致可以分成三类：

![](https://p0.meituan.net/meituantechblog/6ffee1bafd66d006e14e29030226a0c7457553.png)

用户规模正在从少量专业角色扩展到更广人群

- 商家侧仍在探索和试点阶段，规模有限
- 公司内部AI at Work系统中的龙虾（或其他长程Agent）融合更广，用户覆盖产、运、研、销等多类角色
- Skill 的开发门槛越来越低，甚至可以由 AI 辅助生成

这会带来一个直接结论：

> 未来需要评测的人，不只是一小撮产运研同学，而可能是每一个会创建、修改、接入 Skill 的人。

这对评测系统提出了新的要求：

- 要足够简单
- 要足够标准化
- 要足够自动化
- 最好能接入开发与发布流程

**当前的本质痛点**

本质在于 —— 大家不知道怎样写好 Skill，也缺乏对 Skill 全生命周期进行评测的工具。

为了方便大家理解，我们将Skill全生命周期拆解如下：

![](https://p0.meituan.net/meituantechblog/182fee6cd0b3b393e24bf2283bfe024c272940.png)

综上，Skill评测的痛点总体可以拆解成三个方面：

![](https://p1.meituan.net/meituantechblog/281c7582036750d16d76ea3a0c38516d317274.png)

**面向Task的评测**

2026年1月9号，Anthropic发表了一篇博客揭秘 [AI Agent评估](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)，在这篇博客中首次提到了面向Task的长程Agent评测。文中对Task，定义为“具有明确输入和成功标准的单个测试”。

我们综合了Anthropic以及开源软件对Task的定义，简化如下。

![](https://p0.meituan.net/meituantechblog/230f48a442655d73f000d00d39ee8e70190919.png)

prompt定义了我们的问题/诉求，expeted behavior定义了我们预期Agent达成的行为，当我们在正式或测试环境中向Agent发送promt，通过trace获取到长程Agent真实的执行路径，就可以得到（prompt - expeted\_behavior - trace）三元组，类似于短程Agent的（query - ground\_truth - answer），即可进行评测。

**3.2.3 长程Agent评测与短程Agent评测的差异**

可以把两者的差异总结如下：

![](https://p0.meituan.net/meituantechblog/7e18558ac1dcbfe4501f58703ec4fed6197508.png)

最本质的变化是：

> ChatAgent 评测关心“说得好不好”，长程 Agent 评测关心“事情做成没有，以及是怎么做成的”。

**3.2.4 人评主导走向机评主导**

ChatAgent 时代常见流程是：`核心评测员对齐 -> 外包对齐 -> 机评对齐`

而在长程 Agent 场景下，这条链路有机会被明显缩短，甚至可以跳过外包对齐，直接进入：`核心评测员对齐 -> 机评对齐 -> 规模化扩展`

原因主要有三点：

- 长程 Agent 的执行轨迹更丰富，信息密度高使人成为卡点
- Skill 生产门槛低，数量增长极快，人工大规模标注不可持续
- 基座模型能力的持续突破

这并不意味着人工不重要，而是意味着：

- 人工更应该做高价值标准设计和 Rubric 对齐
- AI 更适合承担规模化运行、初筛和回归验证
- 平台更应该承担沉淀、回放、告警和归因职责

换句话说，AI 评测真正要放大的，不是“机器打分”本身，而是核心评测员的判断标准。

**3.2.5 长程Agent评测基建至少应该具备哪些能力**

如果未来要支撑公司内大规模 Agent 和 Skill 生态，评测基础设施至少应包含以下能力：

- **全链路回放**：复现一次任务从输入到结果的全过程
- **Case 管理**：统一维护任务样本、上下文、约束和 Rubric
- **执行沙箱**：按只读、可写、高风险等类型分层隔离执行
- **AI 评测引** 擎：支持 Rubric 驱动的人机对齐和自动判分，且足够简单易用，方便广大skill生产者接入
- **报告与归因**：不仅给分，还能指出问题发生在规划、工具、环境还是 Skill
- **回归机制**：版本升级后自动触发历史 Case 回归
- **准入准出门禁**：把评测结果嵌入开发、发布和运营流程

如果缺少这些能力，评测就容易停留在“单次分析”和“项目制支持”层面，无法真正成为生产系统的一部分。

## [四、总结：Agent评测正在从打分动作走向基础设施能力](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html\#%E5%9B%9B%E3%80%81%E6%80%BB%E7%BB%93-agent%E8%AF%84%E6%B5%8B%E6%AD%A3%E5%9C%A8%E4%BB%8E%E6%89%93%E5%88%86%E5%8A%A8%E4%BD%9C%E8%B5%B0%E5%90%91%E5%9F%BA%E7%A1%80%E8%AE%BE%E6%96%BD%E8%83%BD%E5%8A%9B)

综合来看，随着大模型能力的增强以及Agent Harness的持续演进，Agent 评测的演进可以概括为两句话：

**第一，评测对象变了**

过去评测的是“回答”，现在评测的是“任务系统”。

因此我们关心的不再只是输出内容本身，而是完整执行链路中的能力、稳定性、效率与风险。

**第二，评测方法变了**

过去主流是 `Query -> Answer` 的文本质量评测，现在逐步转向 `Prompt -> Expected Behavior` 的行为评测。

标准答案不再总是唯一，过程质量、任务完成度和轨迹质量成为新的核心对象。

因此，未来真正重要的，不只是能不能做几次评测，而是能不能建设出一套： **看得见问题**、 **说得清标准**、 **跑得动规模**、 **接得上流程**、 **带得动迭代** 的 Agent 评测体系。

* * *

**附：长程Agent评测开源领域的行业调研**

- **任务**（Task，也称 Problem 或 Test Case）：具有明确输入和成功标准的单个测试。每次尝试任务的行动称为试验（Trial）。由于模型输出在不同运行之间会有变化，我们运行多次试验以产生更一致的结果。
- **评分器**（Grader）是评估Agent性能某些方面的逻辑。一个任务可以有多个评分器，每个评分器包含多个断言（有时称为检查 Checks）。
- **记录**（Transcript，也称 Trace 或 Trajectory）：试验的完整记录，包括输出、工具调用、推理、中间结果和任何其他交互。
- **结果**（Outcome）：试验结束时环境的最终状态。航班预订Agent可能在记录末尾说"您的航班已预订"，但结果是环境中 SQL 数据库中是否存在预订记录。
- **评估框架**（Evaluation Harness）：端到端运行评估的基础设施。它提供指令和工具、并发运行任务、记录所有步骤、评分输出并汇总结果。
- **Agent框架**（Agent Harness，或 Scaffold）：使模型能够作为Agent运行的系统：处理输入、编排工具调用并返回结果。当我们评估"一个Agent"时，我们是在评估框架和模型协同工作。例如， [Claude Code](https://claude.com/product/claude-code) 是一个灵活的Agent框架，我们通过 [Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview) 使用其核心原语构建了我们的 [长时间运行Agent框架](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)。
- **评估套件**（Evaluation Suite）：旨在测量特定能力或行为的任务集合。套件中的任务通常共享一个广泛的目标。例如，客户支持评估套件可能测试退款、取消和升级。

![](https://p0.meituan.net/meituantechblog/e389e71bcfa0c0642002ee6c5e068cf81166501.png)

2026年2月，龙虾在全球爆火时候，社区涌现出面向龙虾评测的开源软件：

| 软件名称 | 简介 | GitStar | task定义 |
| --- | --- | --- | --- |
| [pinchbench](https://github.com/pinchbench/skill) | 2026年2月开源，是一套专门用于评估OpenClaw的性能基准测试系统。与传统的合成测试（Synthetic Tests）不同，PinchBench 强调“真实场景下的任务模拟”。它通过给 AI 代理布置实际工作中会遇到的复杂任务，来衡量模型在处理多步工作、实际开发与办公环境下的真实表现。 | 1200+ | md文件 |
| [claw eval](https://github.com/claw-eval/claw-eval) | [北大发布的龙虾能力评测](https://claw-eval.github.io/#/architecture) [task列表](https://claw-eval.github.io/#/tasks)![](https://p0.meituan.net/meituantechblog/965edb20fab8cbfc542bf783c756b4e0266766.png) | 500 | [yaml文件](https://github.com/claw-eval/claw-eval/blob/main/tasks/C12zh_ecommerce_operations/task.yaml) |
| [WildClawBench](https://github.com/InternLM/WildClawBench) | [WildClawBench：野生环境 AI Agent 能力评测 10 大模型谁的"龙虾"最强？](https://www.ai-insight.org/reports/wildclaw-bench-2026) 核心理念是"在野生环境中测试 Agent"——不是给模型一个精心设计的沙盒，而是把它扔进真实用户每天使用 OpenClaw Agent 的场景中，看它能不能活下来。 | 500 | Skill |

![微信扫码关注](https://p0.meituan.net/meituantechblog/6c1215addf43246642526eadeff4275a65525.jpg)

[![LongCat广告](https://p1.meituan.net/meituantechblog/01edae8ea79525da280ce697529fb4a8670633.png)](https://longcat.ai/)

[![技术沙龙](https://p1.meituan.net/meituantechblog/01fab90c3e038efd6fd1c5bedc3096903805590.png)](https://hdxu.cn/1Jpk3)

[![技术招聘](https://p1.meituan.net/meituantechblog/0c57a460539dce970110810e92134fb5164809.png)](https://career.meituan.com/web/home)

[![北斗招聘](https://p1.meituan.net/meituantechblog/ad51e26ed2e9844af5b5bfc6b3af47df138110.jpg)](https://career.meituan.com/web/beidouprogram)

### 推荐阅读

- 1 [美团 LongCat-2.0 正式发布：国产芯片上跑出的万亿参数模型](https://tech.meituan.com/2026/06/30/LongCat2.0.html)
- 2 [用Agent评测思路管理AI Coding：31万行代码AI重构的实践](https://tech.meituan.com/2026/05/07/Agent-AI-Coding.html)
- 3 [LongCat-Next：当视觉和语音成为AI的母语](https://tech.meituan.com/2026/04/02/LongCat-Next.html)
- 4 [美团 EvoCUA 刷新开源 SOTA，会用电脑还会持续进化的智能体！](https://tech.meituan.com/2026/01/26/EvoCUA.html)
- 5 [LongCat-Flash-Thinking-2601 发布，工具调用能力登顶开源 SOTA](https://tech.meituan.com/2026/01/20/LongCat-Flash-Thinking-2601.html)
- 6 [AI Coding与单元测试的协同进化：从验证到驱动](https://tech.meituan.com/2025/12/05/AI-Coding-Unit-Testing.html)
- 7 [2025 \| 美团技术团队热门技术文章汇总](https://tech.meituan.com/2025/12/29/2025-Annual-Review.html)

![美团技术团队](https://p1.meituan.net/meituantechblog/3350d0ad522eaf1b6f0cfebe837ac603112312.png)

CODE A BETTER LIFE

一行代码·亿万生活

美团技术团队，欢迎更多优秀技术人才加入

微信扫码关注美团技术团队