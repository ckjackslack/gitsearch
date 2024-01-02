var app = new Vue({
    el: "#app",
    data: {
        commits: [],
        searchAuthor: "",
        startDate: "",
        endDate: "",
        keyword: "",
        error: null
    },
    methods: {
        fetchCommits: function() {
            const params = new URLSearchParams({
                author: this.searchAuthor,
                since: this.startDate,
                until: this.endDate,
            }).toString();

            fetch(`/commits?${params}`)
                .then(response => response.json())
                .then(data => {
                    this.commits = data;
                })
                .catch(error => {
                    this.error = error;
                });
        }
    },
    mounted: function() {
        this.fetchCommits();
    }
});