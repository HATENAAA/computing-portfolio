# MCArb 复现实验的评估扩展

原始目录是论文 Meta-Collaborative Learning for Arbitrarily Scaled Hyperspectral Image Super-Resolution 的配套代码。本副本完整保留原作者 README（UPSTREAM_README.md）、代码头与 AGPL LICENSE。本次新增 `safe_metrics.py`、`evaluate_cubes.py` 和测试；没有把原论文网络改称本人原创，也没有改动或验证原训练入口。

## 本次完成

提供不依赖 GPU/PyTorch 的独立结果评估入口，显式要求 HWC 数组、data_range 与 scale，输出输入文件 SHA256、逐波段 RMSE、MPSNR/MSSIM/ERGAS/SAM/CC，以及 SAM 空间热图与原始角度数组。

原 `metrics.py` 的 SAM 缺少余弦截断，零光谱可能导致除零；ERGAS/CC 对零均值或常量波段缺少定义边界处理；SSIM 使用旧的关键字接口。本次新增的评估路径修复这些问题。原 `metrics.py` 保留供对照，**训练脚本仍调用原实现**；训练时如要采用新口径需显式替换并重新验证，不应将两个口径的结果混为一张表。

## 运行新增评估

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-eval.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python evaluate_cubes.py pairs.csv --data-range 1 --scale 4 --out runs/eval-x4
```

`pairs.csv` 表头 `truth,prediction`，内容为相对清单路径的 `.npy` 文件，形状 H×W×C；不是直接读取原 MATLAB `.mat`。不得在每张预测上自行 min-max 归一化后评估，否则会改变误差。需要先明确原数据归一化规则与波段顺序，再导出数组。

零光谱 SAM 未定义，报告有效像素数并排除它；零均值波段使 ERGAS 未定义、常量波段使 CC 未定义时返回 null。任意波段精确一致会导致该波段 PSNR 为正无穷，此时 MPSNR 返回 null 并设 psnr_has_infinite_band=true，避免产生无效 JSON。热图以 0..180 度映射蓝到红，灰色为未定义像素。空间边长小于 3 时 SSIM 返回 null。

## 申请材料定位

适合 CIE／AI／数据方向展示实验复现与评价方法理解。下一步使用真实 Pavia/Chikusei 输出，整理固定测试集、随机种子、checkpoint、训练命令、数据划分与消融表。当前未提供权重、数据或历史日志，本次未运行模型训练、未确认“50+ 次训练”，也不补造性能提升。

新增评估工具日期为 2026-10-23，属于毕业设计后的个人扩展；不要把它回填为 2026 年 1—5 月已完成的毕业设计内容。
