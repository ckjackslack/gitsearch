<form @submit.prevent="fetchCommits">
    <div class="field">
        <label class="label">Author:</label>
        <div class="control">
            <input class="input" type="text" v-model="searchAuthor">
        </div>
    </div>

    <div class="field">
        <label class="label">Date Range:</label>
        <div class="control">
            <input class="input" type="date" v-model="startDate">
        </div>
        <div class="control">
            <input class="input" type="date" v-model="endDate">
        </div>
    </div>

    <div class="field">
        <label class="label">Keyword:</label>
        <div class="control">
            <input class="input" type="text" v-model="keyword">
        </div>
    </div>

    <div class="control">
        <button class="button is-link">Search</button>
    </div>
</form>