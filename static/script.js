// Import marked library via CDN
import { marked } from "https://cdn.jsdelivr.net/npm/marked@4.0.12/lib/marked.esm.js";

document.addEventListener("DOMContentLoaded", () => {
  const input = document.querySelector("#user-input");
  const mainContent = document.getElementById("main-content");
  const chatContainer = document.getElementById("chat-container");
  const sendButton = document.querySelector("#send-button");

  // Configure marked for secure rendering
  marked.setOptions({
    gfm: true, // Enable GitHub Flavored Markdown (for tables)
    breaks: true, // Convert newlines to <br> for single line breaks
    sanitize: false, // Allow HTML (since we trust our backend)
    renderer: new marked.Renderer(),
  });

  // Handle suggestion button clicks
  document.querySelectorAll(".question-buttons button:not(.more-questions)").forEach(btn => {
    btn.addEventListener("click", () => {
      input.value = btn.textContent;
      input.focus();
    });
  });

  // Function to handle sending a message
  async function sendMessage() {
    const userMessage = input.value.trim();
    if (!userMessage) return;

    // Show chat container and hide main content
    if (!mainContent.classList.contains("hidden")) {
      mainContent.classList.add("hidden");
      chatContainer.classList.remove("hidden"); // <-- Add this line
    }

    input.disabled = true;
    sendButton.disabled = true;
    input.blur();

    showUserMessage(userMessage);
    input.value = "";

    // Show loading bot message
    const loading = showBotMessage("⏳ Typing...", true);

    try {
      const res = await fetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage })
      });

      const data = await res.json();
      loading.remove();
      showBotMessage(data.reply);
    } catch (err) {
      loading.innerHTML = "⚠️ Failed to connect.";
    } finally {
      input.disabled = false;
      sendButton.disabled = false;
      input.focus();
    }
  }

  // Handle enter key
  input.addEventListener("keypress", async function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      sendMessage();
    }
  });

  // Handle send button click
  sendButton.addEventListener("click", sendMessage);

  // Function to show user message with icon (right side)
  function showUserMessage(text) {
    const row = document.createElement("div");
    row.className = "chat-row user";

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-user-bubble";
    bubble.textContent = text;

    const avatar = document.createElement("img");
    avatar.className = "chat-avatar";
    avatar.src = "/static/user-icon.png";

    row.appendChild(bubble);
    row.appendChild(avatar);
    chatContainer.appendChild(row);
    row.scrollIntoView({ behavior: "smooth" });
  }

  // Function to show bot message with icon and copy button (left side)
  function showBotMessage(text, isLoading = false) {
    const row = document.createElement("div");
    row.className = "chat-row bot";

    const avatar = document.createElement("img");
    avatar.className = "chat-avatar";
    avatar.src = "/static/bot-icon.png";

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bot-bubble";
    if (isLoading) {
      bubble.innerHTML = "<em>⏳Gotcha processing query ...</em>";
    } else {
      bubble.innerHTML = marked.parse(text);

      // Add copy button
      const copyButton = document.createElement("button");
      copyButton.className = "copy-button";
      copyButton.textContent = "Copy";
      copyButton.addEventListener("click", () => {
        const textToCopy = text; // Copy raw markdown
        navigator.clipboard.writeText(textToCopy).then(() => {
          copyButton.classList.add("copied");
          setTimeout(() => copyButton.classList.remove("copied"), 2000);
        });
      });
      bubble.appendChild(copyButton);
    }

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatContainer.appendChild(row);
    row.scrollIntoView({ behavior: "smooth" });

    return bubble;
  }

  // Home title click: reset chat and show main content
  document.getElementById("go-home").addEventListener("click", () => {
    // Hide chat, show main content
    document.getElementById("chat-container").innerHTML = "";
    document.getElementById("chat-container").classList.add("hidden");
    document.getElementById("main-content").classList.remove("hidden");
    // Optionally, clear input
    document.getElementById("user-input").value = "";
  });
});