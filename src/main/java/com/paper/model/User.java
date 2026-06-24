package com.paper.model;

/**
 * 用户实体类
 */
public class User {
    
    private String uname;
    private String password;
    private String email;

    // Getter 和 Setter 方法
    
    public String getUname() {
        return uname;
    }

    public void setUname(String uname) {
        this.uname = uname;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }
}
