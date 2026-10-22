/* gitsearch web UI (Vue 2, no build step). */
var TOKEN_KEY = "gitsearch.token";

function loadToken() {
    try { return window.localStorage.getItem(TOKEN_KEY) || ""; } catch (e) { return ""; }
}

function emptyForm() {
    return { author: "", q: "", path: "", since: "", until: "", merges: "", group_by: "" };
}

new Vue({
    el: "#app",
    data: {
        tab: "search",
        info: null,
        form: emptyForm(),
        result: null,
        groups: null,
        open: {},
        sql: "SELECT author, COUNT(*) AS commits, SUM(insertions) AS added\nFROM commits GROUP BY author ORDER BY commits DESC",
        sqlResult: null,
        examples: [
            "SELECT day, COUNT(*) AS n FROM commits GROUP BY day ORDER BY day DESC LIMIT 14",
            "SELECT path, COUNT(*) AS changes FROM files GROUP BY path ORDER BY changes DESC LIMIT 10",
            "SELECT short_sha, subject, insertions + deletions AS churn FROM commits ORDER BY churn DESC LIMIT 10",
            "SELECT c.author, COUNT(DISTINCT f.path) AS files_touched FROM commits c JOIN files f ON f.sha = c.sha GROUP BY c.author"
        ],
        error: null,
        loading: false,
        needToken: false,
        tokenInput: "",
        token: loadToken()
    },
    computed: {
        groupKeys: function () { return this.info ? this.info.group_keys : []; }
    },
    methods: {
        api: function (path, options) {
            var self = this;
            options = options || {};
            options.headers = options.headers || {};
            if (this.token) options.headers["X-Auth-Token"] = this.token;
            this.loading = true;
            return fetch(path, options).then(function (resp) {
                return resp.json().catch(function () { return {}; }).then(function (body) {
                    self.loading = false;
                    if (resp.status === 401) {
                        self.needToken = true;
                        throw new Error("Unauthorized: enter the access token.");
                    }
                    if (!resp.ok) {
                        throw new Error(body.description || body.title || ("HTTP " + resp.status));
                    }
                    self.needToken = false;
                    return body;
                });
            }, function (err) {
                self.loading = false;
                throw err;
            });
        },
        fail: function (err) { this.error = err.message || String(err); },
        saveToken: function () {
            this.token = this.tokenInput;
            try { window.localStorage.setItem(TOKEN_KEY, this.token); } catch (e) { /* ignore */ }
            this.error = null;
            this.init();
        },
        init: function () {
            var self = this;
            this.api("/api/info").then(function (info) {
                self.info = info;
                self.search(1);
            }).catch(this.fail);
        },
        search: function (page) {
            var self = this;
            var params = new URLSearchParams();
            Object.keys(this.form).forEach(function (k) {
                if (self.form[k]) params.set(k, self.form[k]);
            });
            params.set("page", page || 1);
            this.error = null;
            this.api("/api/commits?" + params.toString()).then(function (data) {
                if (data.groups) { self.groups = data; self.result = null; }
                else { self.result = data; self.groups = null; }
            }).catch(this.fail);
        },
        reset: function () { this.form = emptyForm(); this.search(1); },
        toggle: function (sha) { this.$set(this.open, sha, !this.open[sha]); },
        drillDown: function (key) {
            var g = this.form.group_by;
            if (g === "author" || g === "email") {
                this.form.author = key;
            } else if (g === "day") {
                this.form.since = key; this.form.until = key;
            } else if (g === "month" || g === "year") {
                var parts = key.split("-");
                var y = parseInt(parts[0], 10);
                var m = parts.length > 1 ? parseInt(parts[1], 10) : null;
                var last = m ? new Date(y, m, 0).getDate() : 31;
                this.form.since = m ? key + "-01" : key + "-01-01";
                this.form.until = m ? key + "-" + String(last).padStart(2, "0") : key + "-12-31";
            }
            this.form.group_by = "";
            this.search(1);
        },
        runSql: function () {
            var self = this;
            this.error = null;
            this.api("/api/sql", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: this.sql })
            }).then(function (data) { self.sqlResult = data; }).catch(this.fail);
        }
    },
    mounted: function () { this.init(); }
});
