# Bathymetry Lab · 可复现卫星测深回归

面向匹配后的 Sentinel-2 波段与 ICESat-2 水深样本，提供数据检查、LR／SVR 建模、分组留出评估、模型导出与批量预测。

## 工作流程

1. 检查四波段、深度、分组、采集日期和显式输入单位。
2. 以轨道、场景或空间块分组留出测试集；由 Pipeline 只在训练数据上拟合归一化。
3. 对 LR 与 SVR 输出 RMSE／MAE／R²、逐样本预测、分组和行号、随机种子及输入 SHA256。
4. 保存包含 scaler 的模型；对新样本预测并标记超出训练波段范围或负值的输出，不静默截断。

## 使用

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python pipeline.py samples.csv --units reflectance --out runs/experiment-01
.venv/bin/python predict.py runs/experiment-01/svr.joblib new_samples.csv --units reflectance --output runs/predicted.csv
.venv/bin/python -m unittest discover -s tests -v
```

训练 CSV 表头：`B2,B3,B4,B8,depth_m,group_id,photon_date,image_date`。日期 ISO YYYY-MM-DD，至少 10 条、3 个独立组。默认两类采集时间差不超过一天，`--max-days` 可显式调整并记录于报告。`depth_m` 是校正后的非负水深，不能直接使用未处理的光子高程。

预测 CSV 至少包含 `B2,B3,B4,B8`，可带样本 ID、经纬度等字段，输出将保留。预测命令生成结果 CSV 和 `.metadata.json`，记录模型与输入 SHA256、范围检查结果及异常数量。只加载自己生成或可信来源的 joblib 文件。

`--units dn` 只适用于已确认 offset=0、scale=10000 的数据；其他产品须按其元信息校正后输入反射率。训练和预测均验证反射率在 [0,1]。分组由调用者依据独立性定义，不能用随机行号冒充分组。

## 项目范围

当前模块负责回归阶段，不包含光子去噪、折射校正、大气校正、空间配准和完整 GeoTIFF 生成。输入应先完成质量控制与样本匹配。测试使用合成样本验证数据拆分、单位检查及模型重载，未完成真实海域精度复测。分组 holdout 也不替代多海域外部验证。

预处理依据 [scikit-learn 官方数据泄漏说明](https://scikit-learn.org/stable/common_pitfalls.html)。作品版：2026-10。
