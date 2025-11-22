<script setup>
import { ref } from 'vue';

const API_URL = 'http://localhost:8080'; 

const selectedFile = ref(null);
const uploadCategory = ref('Umowy');
const queryQuestion = ref('');
const searchCategory = ref([]);
const answer = ref(''); // Zmieniono domyślny tekst na pusty
const loading = ref(false);

// NOWA ZMIENNA: Do przechowywania listy plików źródłowych
const sources = ref([]); 

const handleFileUpload = async () => {
    if (!selectedFile.value) return alert('Wybierz plik!');
    loading.value = true;
    const formData = new FormData();
    formData.append('file', selectedFile.value);

    const uploadUrl = `${API_URL}/document/upload?category=${uploadCategory.value}`;

    try {
        const response = await fetch(uploadUrl, { method: 'POST', body: formData });
        const data = await response.json();
        
        if (response.ok) {
            alert(`Plik wgrany! Job ID: ${data.job_id}.`);
        } else {
            alert(`Błąd uploadu: ${data.detail || 'Nieznany błąd'}`);
        }
    } catch (e) {
        alert('Błąd sieci/serwera API.');
    } finally {
        loading.value = false;
    }
};

const handleQuery = async () => {
    if (!queryQuestion.value) return alert('Wpisz pytanie!');

    loading.value = true;
    answer.value = 'Generowanie odpowiedzi...';
    sources.value = []; // Czyścimy źródła przed nowym pytaniem

    const payload = {
        question: queryQuestion.value,
        categories_to_search: searchCategory.value
    };

    try {
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await response.json();

        if (response.ok) {
            answer.value = data.answer;
            // PRZYPISANIE ŹRÓDEŁ: Pobieramy listę ID plików z odpowiedzi backendu
            sources.value = data.source_files || []; 
        } else {
            answer.value = `Błąd RAG: ${data.detail || 'Nieznany błąd'}`;
        }
    } catch (e) {
        answer.value = 'Błąd sieci/serwera LLM Core.';
    } finally {
        loading.value = false;
    }
};
</script>

<template>
    <div id="docuflow-app">
        <h1>📚 DocuFlow - RAG Assistant</h1>
        
        <section>
            <h2>1. Wgraj Dokument</h2>
            <div class="upload-controls">
                <input type="file" @change="e => selectedFile = e.target.files[0]" accept=".pdf" />
                <select v-model="uploadCategory">
                    <option value="Umowy">Umowy</option>
                    <option value="Medyczne">Medyczne</option>
                    <option value="Inne">Inne</option>
                </select>
                <button @click="handleFileUpload" :disabled="loading">
                    {{ loading ? 'Przetwarzanie...' : 'Wgraj do MinIO' }}
                </button>
            </div>
        </section>
        
        <hr/>

        <section>
            <h2>2. Zadaj Pytanie</h2>
            <div class="query-controls">
                <input v-model="queryQuestion" type="text" placeholder="Np. Jaki mam okres wypowiedzenia?" class="query-input"/>
                
                <div class="filters">
                    <label>Szukaj w:</label>
                    <select multiple v-model="searchCategory">
                        <option value="Umowy">Umowy</option>
                        <option value="Medyczne">Medyczne</option>
                        <option value="Inne">Inne</option>
                    </select>
                    <small>(Przytrzymaj Ctrl aby wybrać wiele. Puste = Wszystkie)</small>
                </div>
            </div>

            <button @click="handleQuery" :disabled="loading || !queryQuestion" class="query-btn">
                Uzyskaj Odpowiedź RAG
            </button>
            
            <div v-if="answer && answer !== 'Generowanie odpowiedzi...'" class="answer-box">
                <h3>Odpowiedź AI:</h3>
                <p>{{ answer }}</p>
                
                <div v-if="sources.length > 0" class="sources-box">
                    <h4>📄 Źródła (Kliknij, aby otworzyć):</h4>
                    <ul>
                        <li v-for="src in sources" :key="src">
                            <a :href="`${API_URL}/document/${src}`" target="_blank" class="pdf-link">
                                🔗 {{ src }}.pdf
                            </a>
                        </li>
                    </ul>
                </div>
            </div>
            <div v-else-if="loading && answer === 'Generowanie odpowiedzi...'" class="loading-box">
                {{ answer }}
            </div>
        </section>
    </div>
</template>

<style>
#docuflow-app { max-width: 900px; margin: 0 auto; padding: 20px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
section { border: 1px solid #e0e0e0; padding: 25px; margin-top: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
h1 { color: #2c3e50; text-align: center; }
h2 { margin-top: 0; color: #34495e; }

.upload-controls, .query-controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
input[type="text"] { flex-grow: 1; padding: 10px; border: 1px solid #ccc; border-radius: 4px; }
select { padding: 8px; border-radius: 4px; border: 1px solid #ccc; }
button { padding: 10px 20px; background-color: #42b983; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
button:disabled { background-color: #a0dcb6; cursor: not-allowed; }
button:hover:not(:disabled) { background-color: #3aa876; }

.query-btn { margin-top: 15px; width: 100%; }

.answer-box { margin-top: 25px; border-left: 5px solid #42b983; padding: 20px; background-color: #f9f9f9; border-radius: 4px; color: black}
.answer-box h3 { margin-top: 0; color: #2c3e50; }

/* Style dla źródeł */
.sources-box { margin-top: 15px; padding-top: 10px; border-top: 1px dashed #ccc; font-size: 0.9em; color: #666; }
.sources-box ul { list-style-type: disc; padding-left: 20px; }
.sources-box li { margin-bottom: 5px; font-family: monospace; background: #e8e8e8; display: inline-block; padding: 2px 6px; border-radius: 4px; margin-right: 5px;}

.pdf-link {
    color: #2c3e50;
    text-decoration: none;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 5px;
}
.pdf-link:hover {
    color: #42b983;
    text-decoration: underline;
}
</style>