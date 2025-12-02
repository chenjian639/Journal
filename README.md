# 期刊分析系统 (Journal Analysis System)

基于内容的期刊评价系统 - 国内外同类期刊内容分析、解读与比较

## 技术栈

- **后端**: Java 8+, Servlet, JDBC
- **模板引擎**: Thymeleaf
- **数据库**: MySQL 8.0+
- **连接池**: HikariCP
- **服务器**: Tomcat 9.0+
- **前端**: Bootstrap 5, Font Awesome

## 项目结构

```
JournalAnalysisSystem/
├── pom.xml                          # Maven配置
├── src/
│   └── main/
│       ├── java/com/journal/
│       │   ├── config/              # 配置类
│       │   │   └── ThymeleafConfig.java
│       │   ├── dao/                 # 数据访问层
│       │   │   ├── JournalDao.java
│       │   │   ├── ArticleDao.java
│       │   │   ├── UserDao.java
│       │   │   └── AnalysisReportDao.java
│       │   ├── entity/              # 实体类
│       │   │   ├── Journal.java
│       │   │   ├── Article.java
│       │   │   ├── User.java
│       │   │   └── AnalysisReport.java
│       │   ├── filter/              # 过滤器
│       │   │   ├── AuthFilter.java
│       │   │   └── CharacterEncodingFilter.java
│       │   ├── listener/            # 监听器
│       │   │   └── AppInitListener.java
│       │   ├── service/             # 业务逻辑层
│       │   │   ├── JournalService.java
│       │   │   ├── ArticleService.java
│       │   │   ├── UserService.java
│       │   │   └── AnalysisService.java
│       │   ├── servlet/             # Servlet控制器
│       │   │   ├── BaseServlet.java
│       │   │   ├── IndexServlet.java
│       │   │   ├── AuthServlet.java
│       │   │   ├── JournalServlet.java
│       │   │   └── AnalysisServlet.java
│       │   └── util/                # 工具类
│       │       ├── DBUtil.java
│       │       ├── PasswordUtil.java
│       │       └── StringUtil.java
│       ├── resources/
│       │   ├── db.properties        # 数据库配置
│       │   └── sql/
│       │       └── init.sql         # 数据库初始化脚本
│       └── webapp/
│           └── WEB-INF/
│               ├── web.xml          # Web配置
│               └── templates/       # Thymeleaf模板
│                   ├── index.html
│                   ├── login.html
│                   ├── register.html
│                   ├── journal-list.html
│                   ├── journal-detail.html
│                   ├── journal-form.html
│                   ├── analysis.html
│                   ├── analysis-single.html
│                   ├── analysis-compare.html
│                   ├── analysis-reports.html
│                   ├── analysis-report-detail.html
│                   └── error/
│                       ├── 404.html
│                       └── 500.html
```

## 快速开始

### 1. 环境要求

- JDK 8 或更高版本
- Maven 3.6+
- MySQL 8.0+
- Tomcat 9.0+

### 2. 数据库配置

1. 创建MySQL数据库并执行初始化脚本：

```bash
mysql -u root -p < src/main/resources/sql/init.sql
```

2. 修改数据库连接配置 `src/main/resources/db.properties`：

```properties
db.url=jdbc:mysql://localhost:3306/journal_analysis?useSSL=false&serverTimezone=Asia/Shanghai
db.username=root
db.password=你的密码
```

### 3. 编译打包

```bash
mvn clean package
```

### 4. 部署到Tomcat

将生成的 `target/JournalAnalysisSystem.war` 复制到 Tomcat 的 `webapps` 目录下，启动Tomcat即可。

### 5. 访问系统

打开浏览器访问：http://localhost:8080/JournalAnalysisSystem

默认管理员账号：
- 用户名：admin
- 密码：admin123

## 功能模块

### 已实现功能

- ✅ 用户注册/登录/登出
- ✅ 期刊列表展示与搜索
- ✅ 期刊详情查看
- ✅ 期刊添加/编辑（管理员）
- ✅ 基本的分析页面框架

### 待实现功能 (TODO)

- 📋 期刊内容深度分析
  - 发文趋势分析
  - 热点关键词挖掘
  - 高产作者统计
  - 引用分析
- 📋 多期刊比较分析
  - 影响因子对比
  - 研究主题对比
  - 国际化程度对比
- 📋 国内外期刊对比
- 📋 分析报告生成与导出
- 📋 数据可视化图表
- 📋 论文数据管理
- 📋 数据导入功能

## 开发说明

### 添加新的Servlet

1. 创建Servlet类，继承 `BaseServlet`
2. 使用 `@WebServlet` 注解配置URL映射
3. 使用 `render()` 方法渲染Thymeleaf模板

### 添加新的模板

1. 在 `WEB-INF/templates/` 目录下创建HTML文件
2. 使用Thymeleaf语法 `th:` 进行数据绑定

### 分析功能扩展点

核心分析逻辑在 `AnalysisService.java` 中，主要方法：

- `analyzeJournal(Long journalId)` - 单期刊分析
- `compareJournals(List<Long> journalIds)` - 多期刊比较
- `compareDomesticAndInternational(String category)` - 国内外对比

## 许可证

MIT License
