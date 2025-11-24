<script setup>
import { ref, computed } from "vue";

// --- LOGIC ---
const API_URL = "http://localhost:8080";

// State
const selectedFile = ref(null);
const uploadCategory = ref("Umowy");
const queryQuestion = ref("");
const searchCategory = ref([]);
const answer = ref("");
const loading = ref(false);
const sources = ref([]);
const uploadStatus = ref(""); // Zamiast alertów
const isDragging = ref(false);

// Helper: Format file size
const formatSize = (bytes) => {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
};

// File Handling
const onFileChange = (e) => {
  const file = e.target.files[0];
  if (file) selectedFile.value = file;
};

const onDrop = (e) => {
  isDragging.value = false;
  const file = e.dataTransfer.files[0];
  if (file && file.type === "application/pdf") {
    selectedFile.value = file;
  } else {
    uploadStatus.value = "Only PDF files are supported.";
  }
};

const handleFileUpload = async () => {
  if (!selectedFile.value) {
    uploadStatus.value = "⚠️ Select the file before sending.";
    return;
  }
  loading.value = true;
  uploadStatus.value = "";

  const formData = new FormData();
  formData.append("file", selectedFile.value);

  const uploadUrl = `${API_URL}/document/upload?category=${uploadCategory.value}`;

  try {
    const response = await fetch(uploadUrl, { method: "POST", body: formData });
    const data = await response.json();

    if (response.ok) {
      uploadStatus.value = `✅ Success! Job ID: ${data.job_id}`;
      selectedFile.value = null; // Reset po sukcesie
    } else {
      uploadStatus.value = `❌ Error: ${data.detail || "Unknown error"}`;
    }
  } catch (e) {
    uploadStatus.value = "❌ Network/API server error.";
  } finally {
    loading.value = false;
  }
};

const handleQuery = async () => {
  if (!queryQuestion.value) return;
  loading.value = true;
  answer.value = "";
  sources.value = [];

  const categoriesToSearch = searchCategory.value.length > 0 
    ? searchCategory.value 
    : ["Umowy", "Medyczne", "Inne"]; // Domyślnie szukaj wszędzie jak nic nie wybrano

  const payload = {
    question: queryQuestion.value,
    categories_to_search: categoriesToSearch,
  };

  try {
    const response = await fetch(`${API_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (response.ok) {
      answer.value = data.answer || "No response.";
      sources.value = data.source_files || [];
    } else {
      answer.value = `Error RAG: ${data.detail || "Unknown error"}`;
    }
  } catch (e) {
    answer.value = "Error connecting to the model.";
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div>
    
    <!-- Background Effects (Glows) -->
    <div class="absolute top-0 left-1/4 w-96 h-96 bg-indigo-600/20 rounded-full blur-[128px] pointer-events-none"></div>
    <div class="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-600/10 rounded-full blur-[128px] pointer-events-none"></div>

    <div class="max-w-7xl mx-auto px-4 py-8 relative z-10 flex flex-col h-screen">
      
      <!-- Header -->
      <header class="flex items-center justify-between mb-12 animate-fade-in-down">
        <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" viewBox="0 0 32 32" fill="none">
                <!-- Dokument (Biały obrys) -->
                <path d="M10 8h12c1.1 0 2 .9 2 2v14c0 1.1-.9 2-2 2H10c-1.1 0-2-.9-2-2V10c0-1.1.9-2 2-2z" stroke="white" stroke-width="2" stroke-opacity="0.9" fill="none"/>
                <!-- Linie tekstu w dokumencie -->
                <path d="M14 13h8M14 17h8M14 21h4" stroke="white" stroke-width="2" stroke-linecap="round" stroke-opacity="0.6"/>
                
                <!-- Błysk AI / Gwiazdka (Cyan - ten sam co w faviconie) -->
                <path d="M26 4l1 2 2 1-2 1-1 2-1-2-2-1 2-1z" fill="#22d3ee" />
                </svg>
            </div>
          <div>
            <h1 class="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-slate-400">
              Document Flow <span class="text-indigo-400 font-light text-base">RAG</span>
            </h1>
            <p class="text-xs text-slate-500 font-medium tracking-wider">powered by LangChain</p>
          </div>
        </div>
        <div class="text-xs px-3 py-1 rounded-full border border-slate-800 bg-slate-900/50 text-slate-400">
          v2.0 • Connected
        </div>
      </header>

      <!-- Main Grid Layout -->
      <main class="flex-1 grid grid-cols-1 lg:grid-cols-50 gap-6 h-full pb-4 mt-12">
        
        <!-- LEFT COLUMN: Configuration & Upload (Glass Card) -->
        <aside class="lg:col-span-20 flex flex-col gap-6 animate-fade-in-left">
          <div class="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-3xl p-6 shadow-2xl flex flex-col gap-6 h-full">
            
            <!-- Section Title -->
            <div>
              <h2 class="text-lg font-semibold text-white flex items-center gap-2">
                Knowledge Base
              </h2>
              
            </div>

            <!-- Dropzone -->
            <div
              @dragover.prevent="isDragging = true"
              @dragleave.prevent="isDragging = false"
              @drop.prevent="onDrop"
              class="relative group border-2 border-dashed rounded-2xl transition-all duration-300 flex flex-col items-center justify-center p-8 text-center cursor-pointer"
              :class="isDragging ? 'border-indigo-500 bg-indigo-500/10' : 'border-slate-700 hover:border-slate-500 hover:bg-slate-800/50'"
            >
              <input type="file" accept=".pdf" class="absolute inset-0 opacity-0 cursor-pointer" @change="onFileChange" />
              
              <div v-if="!selectedFile" class="pointer-events-none flex flex-col items-center justify-center text-center w-full">
                <div class="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform shadow-lg">
                  <svg class="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
                </div>
                <p class="text-sm font-medium text-slate-300">Click or drop a PDF</p>
                <p class="text-xs text-slate-500 mt-1">Maximum 10MB</p>
              </div>

              <div v-else class="flex items-center gap-3 pointer-events-none">
                <div class="w-10 h-10 bg-red-500/20 text-red-400 rounded-lg flex items-center justify-center">
                  <span class="font-bold text-xs">PDF</span>
                </div>
                <div class="text-left">
                  <p class="text-sm font-medium text-white truncate max-w-[180px]">{{ selectedFile.name }}</p>
                  <p class="text-xs text-slate-500">{{ formatSize(selectedFile.size) }}</p>
                </div>
              </div>
            </div>

            <!-- Category Select -->
            <div class="space-y-2">
              <label class="text-xs font-bold uppercase tracking-wider text-slate-500">File category</label>
              <div class="relative">
                <select v-model="uploadCategory" class="w-full bg-slate-800/50 text-white border border-slate-700 rounded-xl px-4 py-3 appearance-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all">
                  <option value="Umowy">Umowy</option>
                  <option value="Medyczne">Dokumentacja Medyczna</option>
                  <option value="Inne">Inne</option>
                </select>
                <div class="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                </div>
              </div>
            </div>

            <!-- Upload Button -->
            <button
              @click="handleFileUpload"
              :disabled="loading || !selectedFile"
              class="w-full py-3.5 rounded-xl font-bold text-sm transition-all transform active:scale-95 flex items-center justify-center gap-2 shadow-lg shadow-indigo-900/20"
              :class="loading || !selectedFile ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white hover:brightness-110 hover:shadow-indigo-500/40'"
            >
              <span v-if="loading && selectedFile" class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full"></span>
              {{ loading ? 'Uploading...' : 'Upload' }}
            </button>

            <!-- Status Message -->
            <div v-if="uploadStatus" class="text-xs text-center font-medium animate-pulse" :class="uploadStatus.includes('Sukces') ? 'text-emerald-400' : 'text-rose-400'">
              {{ uploadStatus }}
            </div>


          </div>
        </aside>

        <!-- RIGHT COLUMN: Chat & Interaction -->
        <section class="lg:col-span-30 flex flex-col animate-fade-in-right h-full">
          <div class="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-3xl p-6 shadow-2xl flex flex-col h-full relative overflow-hidden">
            
            <!-- Empty State (Before Search) -->
            <div v-if="!answer && !loading" class="flex-1 flex flex-col items-center justify-center text-center opacity-60">
              <div class="w-20 h-20 bg-slate-800/50 rounded-full flex items-center justify-center mb-6 border border-white/5">
                <svg class="w-10 h-10 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
              </div>
              <h3 class="text-xl font-semibold text-white mb-2">How can I help you?</h3>
              <p class="text-slate-400 max-w-md mb-2">Ask a question about uploaded documents. I will search Chroma's vector databases to find a precise answer.</p>
              
              <!-- Suggestion Chips -->
              <div class="flex flex-wrap justify-center gap-2 mt-12">
                <button @click="queryQuestion = 'Jaki jest okres wypowiedzenia?'; handleQuery()" class="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-4 py-2 rounded-full transition-colors">
                  Jaki jest okres wypowiedzenia?
                </button>
                <button @click="queryQuestion = 'Jakie zalecenia medyczne dla Marty Z.?'; handleQuery()" class="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-4 py-2 rounded-full transition-colors">
                  Jakie zalecenia medyczne dla Marty Z.?
                </button>
              </div>
            </div>

            <!-- Result Area -->
            <div v-else class="flex-1 overflow-y-auto custom-scrollbar pr-2 mb-6 space-y-6">
              <!-- User Question Bubble -->
              <div class="flex justify-end">
                <div class="bg-slate-800 text-white px-6 py-4 rounded-2xl rounded-tr-sm max-w-[80%] shadow-md">
                  <p>{{ queryQuestion }}</p>
                </div>
              </div>

              <!-- AI Loading -->
              <div v-if="loading" class="flex gap-4 max-w-[90%] animate-pulse">
                <div class="w-10 h-10 rounded-full bg-indigo-600 flex-shrink-0 flex items-center justify-center">
                  <svg class="w-6 h-6 text-white animate-spin-slow" fill="none" viewBox="0 0 24 24"><path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg>
                </div>
                <div class="space-y-3 w-full">
                  <div class="h-4 bg-slate-800 rounded w-3/4"></div>
                  <div class="h-4 bg-slate-800 rounded w-1/2"></div>
                  <div class="h-4 bg-slate-800 rounded w-5/6"></div>
                </div>
              </div>

              <!-- AI Answer -->
              <div v-if="answer && !loading" class="flex gap-4 animate-fade-in-up">
                <div class="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-600 to-purple-600 flex-shrink-0 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                  <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                </div>
                
                <div class="space-y-4 max-w-[90%]">
                  <div class="prose prose-invert prose-sm bg-transparent text-slate-200 leading-relaxed">
                   <!-- Simple replacement for markdown rendering, in real app use marked or similar -->
                    <p>{{ answer }}</p>
                  </div>

                  <!-- Sources Section -->
                  <div v-if="sources.length > 0" class="pt-4 border-t border-white/10">
                    <p class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path></svg>
                      Sources
                    </p>
                    <div class="flex flex-wrap gap-2">
                      <a
                        v-for="src in sources"
                        :key="src"
                        :href="`${API_URL}/document/${src}`"
                        target="_blank"
                        class="group flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-indigo-600/20 border border-slate-700 hover:border-indigo-500/50 rounded-lg transition-all duration-200 cursor-pointer text-xs text-slate-300 hover:text-indigo-300"
                      >
                        <svg class="w-3 h-3 text-slate-500 group-hover:text-indigo-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd"></path></svg>
                        {{ src }}.pdf
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Input Area (Fixed at bottom) -->
            <div class="mt-auto bg-slate-800/50 p-2 rounded-2xl border border-slate-700/50 flex items-end gap-2 focus-within:border-indigo-500/50 focus-within:ring-1 focus-within:ring-indigo-500/50 transition-all shadow-lg">
              
              <!-- Filters Toggle (Simplified for UI) -->
              <div class="relative group">
                 <select multiple v-model="searchCategory" class="absolute inset-0 w-10 opacity-0 cursor-pointer z-10"></select>
                 <button class="p-3 text-slate-400 hover:text-white hover:bg-slate-700 rounded-xl transition-colors" title="Filtruj kategorie">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
                 </button>
                 <!-- Tooltip/Indicator -->
                 <span v-if="searchCategory.length > 0" class="absolute top-2 right-2 w-2 h-2 bg-indigo-500 rounded-full"></span>
              </div>

              <input
                v-model="queryQuestion"
                @keyup.enter="handleQuery"
                type="text"
                placeholder="Ask a question about your documents..."
                class="w-full bg-transparent border-none text-white placeholder-slate-500 focus:ring-0 py-3.5 px-2 text-base"
              />

              <button
                @click="handleQuery"
                :disabled="!queryQuestion || loading"
                class="p-3 rounded-xl transition-all duration-200 flex items-center justify-center"
                :class="!queryQuestion || loading ? 'bg-slate-700 text-slate-500' : 'bg-indigo-600 text-white hover:bg-indigo-500 shadow-lg shadow-indigo-600/20'"
              >
                <svg class="w-5 h-5 transform rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
              </button>
            </div>
             <p class="text-[10px] text-slate-600 text-center mt-2">Model can generate inaccurate information. Check sources.</p>

          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
/* Custom Scrollbar for the Chat Area */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(30, 41, 59, 0.5);
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(71, 85, 105, 0.8);
  border-radius: 20px;
}

/* Animations */
.animate-fade-in-down {
  animation: fadeInDown 0.6s ease-out;
}
.animate-fade-in-left {
  animation: fadeInLeft 0.6s ease-out 0.2s both;
}
.animate-fade-in-right {
  animation: fadeInRight 0.6s ease-out 0.4s both;
}
.animate-fade-in-up {
  animation: fadeInUp 0.4s ease-out;
}

@keyframes fadeInDown {
  from { opacity: 0; transform: translateY(-20px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes fadeInLeft {
  from { opacity: 0; transform: translateX(-20px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes fadeInRight {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-spin-slow {
  animation: spin 3s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>