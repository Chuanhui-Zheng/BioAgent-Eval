# CS46 本轮实现交付说明

已保存到原项目，当前预览：http://127.0.0.1:5180/ 。

完成：真实 RNA/蛋白表达查询；2hrG 和 2hrFFA 的 Manhattan/QQ 与区域查询；真实 GO/WikiPathways 注释；矩阵及 W/H 上传解析；NMF 和 Bayesian NMF；效应值筛选；本地超几何富集与 BH 校正；结果/证据报告导出；独立标注评估和人工审核表；科学数值引用核对；Docker 与 CI 配置。

数据覆盖：2hrFFA 448,162 条、2hrG 197,779 条变异统计；蛋白表达 1,479,446 条观测；RNA 132,904 条原始统计行。公共库为 WikiPathways_2024_Human 和 GO_Biological_Process_2026，来源与校验值保存在项目中。

验证：193 项测试、55 项子测试通过，包括 FAISS；前端构建通过；真实 API 和浏览器中的语料矩阵→10 个基因筛选→本地富集流程已验证。此次真实选择没有通路达到 BH q≤0.05，系统如实返回零显著结果。

尚未实测：真实 AIHubMix key 的线上调用；Docker 容器启动（本机无 Docker）；远程 CI 运行。人工盲测标签和科学结论审核不能由自动测试代替。Bayesian NMF 已实现采样和区间，但单链收敛未被声称为已验证。

运行方式、文件格式、方法与限制已写入项目 README。结构化缓存约 714 MB，属于可重建文件，不提交版本库；分析会话支持导出，重启后需重新载入。

方法参考：
- https://mlg.eng.cam.ac.uk/pub/pdf/SchWinHan09.pdf
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.hypergeom.html
- https://maayanlab.cloud/Enrichr/
