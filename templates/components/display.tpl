{% raw %}
<div class="section">
    <div v-if="commits.length">
        <div v-for="commit in commits" :key="commit.commit" class="box">
            <p><strong>Author:</strong> {{ commit.author }}</p>
            <p><strong>Commit:</strong> {{ commit.commit }}</p>
            <p><strong>Date:</strong> {{ commit.date }}</p>
            <p><strong>Message:</strong> {{ commit.message }}</p>
            <p><strong>Files:</strong>
            <ul>
                <li v-for="file in commit.files" :key="file[0]">
                    <span class="highlighted">{{ file[0] }}</span> (<span class="green">+{{ file[1] }}</span>, <span class="red">-{{ file[2] }}</span>)
                </li>
            </ul>
        </div>
    </div>
    <div v-else>
        <p>No commits found.</p>
    </div>
</div>
{% endraw %}