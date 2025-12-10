package com.journal.service;

import com.journal.dao.ArticleDao;
import com.journal.dao.JournalDao;
import com.journal.entity.Article;
import com.journal.entity.Journal;

import java.util.List;

/**
 * 论文服务层
 */
public class ArticleService {
    private ArticleDao articleDao = new ArticleDao();
    private JournalDao journalDao = new JournalDao();

    /**
     * 添加论文
     */
    public Long addArticle(Article article) {
        return articleDao.insert(article);
    }

    /**
     * 根据ID获取论文
     */
    public Article getArticleById(Long id) {
        Article article = articleDao.findById(id);
        if (article != null && article.getJournalId() != null) {
            Journal journal = journalDao.findById(article.getJournalId());
            article.setJournal(journal);
        }
        return article;
    }

    /**
     * 获取期刊的论文列表
     */
    public List<Article> getArticlesByJournalId(Long journalId) {
        return articleDao.findByJournalId(journalId);
    }

    /**
     * 搜索论文
     */
    public List<Article> searchArticles(String keyword) {
        return articleDao.search(keyword);
    }

    /**
     * 统计期刊论文数量
     */
    public int getArticleCountByJournalId(Long journalId) {
        return articleDao.countByJournalId(journalId);
    }

    /**
     * 删除论文
     */
    public boolean deleteArticle(Long id) {
        return articleDao.delete(id);
    }
}
