package com.paper.controller;

import java.sql.SQLException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.multipart.MultipartFile;

import com.paper.service.AdminService;
import com.paper.utils.ResponseUtils;
import com.paper.utils.ValidationUtils;

@Controller
@RequestMapping("/admin")
public class AdminController {

    private final AdminService adminService;

    public AdminController(AdminService adminService) {
        this.adminService = adminService;
    }

    @GetMapping("/me")
    @ResponseBody
    public Map<String, Object> me(@RequestParam String uname) {
        if (ValidationUtils.isBlank(uname)) {
            return ResponseUtils.error("用户名不能为空");
        }
        try {
            boolean isAdmin = adminService.isAdmin(uname.trim());
            Map<String, Object> data = new HashMap<>();
            data.put("isAdmin", isAdmin);
            return ResponseUtils.success("success", data);
        } catch (SQLException e) {
            return ResponseUtils.error("管理员校验失败: " + e.getMessage());
        }
    }

    @GetMapping("/stats")
    @ResponseBody
    public Map<String, Object> stats(@RequestParam String uname) {
        if (ValidationUtils.isBlank(uname)) {
            return ResponseUtils.error("用户名不能为空");
        }
        try {
            if (!adminService.isAdmin(uname.trim())) {
                return ResponseUtils.error("无权限");
            }
            Map<String, Object> stats = adminService.getSystemStats();
            Map<String, Object> data = new HashMap<>();
            data.put("stats", stats);
            return ResponseUtils.success("success", data);
        } catch (SQLException e) {
            return ResponseUtils.error("获取统计失败: " + e.getMessage());
        }
    }

    @GetMapping("/users")
    @ResponseBody
    public Map<String, Object> listUsers(@RequestParam String uname) {
        if (ValidationUtils.isBlank(uname)) {
            return ResponseUtils.error("用户名不能为空");
        }
        try {
            if (!adminService.isAdmin(uname.trim())) {
                return ResponseUtils.error("无权限");
            }
            List<Map<String, Object>> users = adminService.listUsers();
            Map<String, Object> data = new HashMap<>();
            data.put("users", users);
            return ResponseUtils.success("success", data);
        } catch (SQLException e) {
            return ResponseUtils.error("获取用户列表失败: " + e.getMessage());
        }
    }

    @PostMapping("/users/delete")
    @ResponseBody
    public Map<String, Object> deleteUser(
        @RequestParam String uname,
        @RequestParam String targetUname
    ) {
        if (ValidationUtils.isBlank(uname) || ValidationUtils.isBlank(targetUname)) {
            return ResponseUtils.error("用户名不能为空");
        }
        String actor = uname.trim();
        String target = targetUname.trim();

        try {
            if (!adminService.isAdmin(actor)) {
                return ResponseUtils.error("无权限");
            }
            if (actor.equals(target)) {
                return ResponseUtils.error("不能删除当前登录用户");
            }

            adminService.deleteUserCascade(target);
            return ResponseUtils.success("删除成功");
        } catch (SQLException e) {
            return ResponseUtils.error("删除失败: " + e.getMessage());
        } catch (IllegalStateException e) {
            return ResponseUtils.error(e.getMessage());
        }
    }

    @PostMapping("/users/reset-password")
    @ResponseBody
    public Map<String, Object> resetPassword(
        @RequestParam String uname,
        @RequestParam String targetUname,
        @RequestParam(required = false) String newPassword
    ) {
        if (ValidationUtils.isBlank(uname) || ValidationUtils.isBlank(targetUname)) {
            return ResponseUtils.error("用户名不能为空");
        }
        String actor = uname.trim();
        String target = targetUname.trim();

        try {
            if (!adminService.isAdmin(actor)) {
                return ResponseUtils.error("无权限");
            }

            String pwd = (newPassword == null) ? "" : newPassword;
            if (!pwd.isBlank()) {
                String err = ValidationUtils.validatePassword(pwd);
                if (err != null) {
                    return ResponseUtils.error(err);
                }
            }

            String actualNewPwd = adminService.resetUserPassword(target, pwd);
            Map<String, Object> data = new HashMap<>();
            data.put("newPassword", actualNewPwd);
            return ResponseUtils.success("success", data);
        } catch (SQLException e) {
            return ResponseUtils.error("重置密码失败: " + e.getMessage());
        } catch (IllegalStateException e) {
            return ResponseUtils.error(e.getMessage());
        }
    }

    // =========================
    // Papers: import + search
    // =========================

    @PostMapping("/papers/preview")
    @ResponseBody
    public Map<String, Object> previewPapers(
        @RequestParam String uname,
        @RequestParam(required = false, defaultValue = "csv") String format,
        @RequestParam("file") MultipartFile file
    ) {
        if (ValidationUtils.isBlank(uname)) {
            return ResponseUtils.error("用户名不能为空");
        }
        try {
            if (!adminService.isAdmin(uname.trim())) {
                return ResponseUtils.error("无权限");
            }
            Map<String, Object> data = adminService.previewPapers(file, format);
            return ResponseUtils.success("success", data);
        } catch (Exception e) {
            return ResponseUtils.error("预览失败: " + e.getMessage());
        }
    }

    @PostMapping("/papers/import")
    @ResponseBody
    public Map<String, Object> importPapers(
        @RequestParam String uname,
        @RequestParam(required = false, defaultValue = "csv") String format,
        @RequestParam("file") MultipartFile file,

        // 映射：这些值是“文件中的列名”
        @RequestParam(required = false) String map_title,
        @RequestParam(required = false) String map_doi,
        @RequestParam(required = false) String map_journal,
        @RequestParam(required = false) String map_keywords,
        @RequestParam(required = false) String map_publish_date,
        @RequestParam(required = false) String map_abstract,
        @RequestParam(required = false) String map_target,

        // 筛选
        @RequestParam(required = false) Integer minYear,
        @RequestParam(required = false) Integer maxYear,
        @RequestParam(required = false, defaultValue = "true") boolean requireTitle
    ) {
        if (ValidationUtils.isBlank(uname)) {
            return ResponseUtils.error("用户名不能为空");
        }
        try {
            if (!adminService.isAdmin(uname.trim())) {
                return ResponseUtils.error("无权限");
            }

            Map<String, String> mapping = new HashMap<>();
            if (!ValidationUtils.isBlank(map_title)) mapping.put("title", map_title.trim());
            if (!ValidationUtils.isBlank(map_doi)) mapping.put("doi", map_doi.trim());
            if (!ValidationUtils.isBlank(map_journal)) mapping.put("journal", map_journal.trim());
            if (!ValidationUtils.isBlank(map_keywords)) mapping.put("keywords", map_keywords.trim());
            if (!ValidationUtils.isBlank(map_publish_date)) mapping.put("publish_date", map_publish_date.trim());
            if (!ValidationUtils.isBlank(map_abstract)) mapping.put("abstract", map_abstract.trim());
            if (!ValidationUtils.isBlank(map_target)) mapping.put("target", map_target.trim());

            Map<String, Object> data = adminService.importPapers(file, format, mapping, minYear, maxYear, requireTitle);
            return ResponseUtils.success("success", data);
        } catch (Exception e) {
            return ResponseUtils.error("导入失败: " + e.getMessage());
        }
    }

    @GetMapping("/papers/search")
    @ResponseBody
    public Map<String, Object> searchPapers(
        @RequestParam String uname,
        @RequestParam(required = false, defaultValue = "") String q,
        @RequestParam(required = false, defaultValue = "50") int limit,
        @RequestParam(required = false, defaultValue = "0") int offset
    ) {
        if (ValidationUtils.isBlank(uname)) {
            return ResponseUtils.error("用户名不能为空");
        }
        try {
            if (!adminService.isAdmin(uname.trim())) {
                return ResponseUtils.error("无权限");
            }
            Map<String, Object> data = adminService.searchPapers(q, limit, offset);
            return ResponseUtils.success("success", data);
        } catch (Exception e) {
            return ResponseUtils.error("检索失败: " + e.getMessage());
        }
    }

    @GetMapping("/papers/detail/{id}")
    @ResponseBody
    public Map<String, Object> paperDetail(
        @RequestParam String uname,
        @PathVariable("id") long id
    ) {
        if (ValidationUtils.isBlank(uname)) {
            return ResponseUtils.error("用户名不能为空");
        }
        try {
            if (!adminService.isAdmin(uname.trim())) {
                return ResponseUtils.error("无权限");
            }
            Map<String, Object> paper = adminService.getPaperDetail(id);
            Map<String, Object> data = new HashMap<>();
            data.put("paper", paper);
            return ResponseUtils.success("success", data);
        } catch (Exception e) {
            return ResponseUtils.error("获取详情失败: " + e.getMessage());
        }
    }
}
