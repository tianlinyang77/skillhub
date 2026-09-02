# 贡献模板

模板有意设计为不可发现：所有脚手架专用文件使用 `.template` 后缀。发布包会
拒绝任何残留 `.template` 文件。

优先使用 `python3 scripts/new_skill.py --help`：脚本会写入最终文件名、填写
确定性身份字段、复制已审核许可证材料并生成 component 注册。默认直接生成到
本仓库 `skills/`；只有显式传入远端 `--repo` 时才生成到产品仓 checkout。
这里的模板只作为手工 fallback。

手工创建时，把 `templates/skill/` 复制到本仓库的 `skills/<skill-name>/`，
根据 `README.md.template` 重命名软件包文件，删除脚手架 README，替换所有
占位符，并在申请目录准入前对独立安装目录执行校验。
