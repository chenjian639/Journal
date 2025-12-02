package com.journal.service;

import com.journal.dao.JournalDao;
import com.journal.entity.Journal;

import java.util.List;

/**
 * 期刊服务层
 */
public class JournalService {
    private JournalDao journalDao = new JournalDao();

    /**
     * 添加期刊
     */
    public Long addJournal(Journal journal) {
        return journalDao.insert(journal);
    }

    /**
     * 更新期刊
     */
    public boolean updateJournal(Journal journal) {
        return journalDao.update(journal);
    }

    /**
     * 删除期刊
     */
    public boolean deleteJournal(Long id) {
        return journalDao.delete(id);
    }

    /**
     * 根据ID获取期刊
     */
    public Journal getJournalById(Long id) {
        return journalDao.findById(id);
    }

    /**
     * 获取所有期刊
     */
    public List<Journal> getAllJournals() {
        return journalDao.findAll();
    }

    /**
     * 分页获取期刊
     */
    public List<Journal> getJournalsByPage(int page, int pageSize) {
        return journalDao.findByPage(page, pageSize);
    }

    /**
     * 搜索期刊
     */
    public List<Journal> searchJournals(String keyword, String country, String category) {
        return journalDao.search(keyword, country, category);
    }

    /**
     * 获取期刊总数
     */
    public int getJournalCount() {
        return journalDao.count();
    }

    /**
     * 按国家统计期刊
     */
    public List<Object[]> getJournalCountByCountry() {
        return journalDao.countByCountry();
    }
}
