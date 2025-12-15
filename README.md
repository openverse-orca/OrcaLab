# OrcaLab

OrcaLab是松应科技推出的轻量化AI based具身智能仿真平台和SimReady 资产库，其核心定位是降低前沿技术的使用门槛，让开发者、研究人员和初创团队能够更便捷、高效地触及并应用高精度物理仿真能力。与传统重型仿真平台相比，OrcaLab继承了其核心产品ORCA平台的关键技术基因，致力于在轻量化的架构上，为用户提供开箱即用的便捷体验。它支持多种形态的机器人仿真训练，并能快速构建覆盖家庭、商超、工业等典型场景的高精度数字训练场。平台特别注重提升数据生成与算法训练的效率，其并发训练能力可以大幅缩短机器人的开发与测试周期。OrcaLab旨在成为连接创意与实现的桥梁，通过提供轻量化、易用且功能强大的仿真环境，赋能更广泛的群体探索具身智能的无限可能，从而加速创新生态的构建与繁荣。

## 功能特性

TODO: 待补充

## 系统要求

### 硬件需求

| 配置类型 | CPU | 内存 | GPU |
|--------|-----|------|-----|
| 最低配置 | Intel i5 或同等性能 | 32GB 以上 | Nvidia RTX 3060 或同等性能 |
| 推荐配置 | Intel i7 13700 以上 | 64GB 以上 | Nvidia RTX 4090 或同等性能 |

### 操作系统需求

| 操作系统 | 内核版本 |
|--------|--------|
| Ubuntu 22.04 LTS | 6.8 及以上 |
| Ubuntu 24.04 LTS | 6.8 及以上 |

## 安装

```bash
pip install orca-lab
```

详见 [INSTALL.md](INSTALL.md)

**网络提示**：国内用户如遇到网络问题，请使用梯子或配置清华源：
```bash
pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
```

## 使用方法

### 启动方式

安装后使用命令行启动：
```bash
orcalab
```

## 常见问题

用户和开发者常见的问题及解决方案：
- 用户相关：参考 [INSTALL.md](INSTALL.md) 和 [Docs/DEVELOPMENT_INSTALLATION.md](Docs/DEVELOPMENT_INSTALLATION.md)
- 开发相关：参考 [Docs/DEVELOPMENT_FAQ.md](Docs/DEVELOPMENT_FAQ.md)


## 许可证

本项目采用 [LICENSE](LICENSE) 文件中规定的许可证条款。