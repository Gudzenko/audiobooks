(() => {
  const form = document.getElementById("chat-form");
  if (!form) return;

  const messages = document.getElementById("chat-messages");
  const input = document.getElementById("chat-input");
  const submit = document.getElementById("chat-submit");
  const clear = document.getElementById("clear-chat");
  const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]").value;
  let history = [];
  let isSending = false;
  const maxHistoryItems = Number(form.dataset.historyItemLimit);
  const maxHistoryCharacters = Number(form.dataset.historyCharacterLimit);

  const trimHistory = () => {
    history = history.slice(-maxHistoryItems);
    let totalCharacters = history.reduce(
      (total, item) => total + item.content.length,
      0,
    );
    while (history.length > 1 && totalCharacters > maxHistoryCharacters) {
      totalCharacters -= history[0].content.length;
      history.shift();
    }
  };

  const scrollToBottom = () => {
    messages.scrollTop = messages.scrollHeight;
  };

  const addBubble = (role, content, className = "", safeHtml = "") => {
    const article = document.createElement("article");
    article.className = `chat-message chat-message-${role} ${className}`.trim();
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    if (safeHtml) {
      bubble.classList.add("chat-bubble-rich");
      bubble.innerHTML = safeHtml;
    } else {
      bubble.textContent = content;
    }
    article.appendChild(bubble);
    messages.appendChild(article);
    scrollToBottom();
    return article;
  };

  const addResponse = (response) => {
    const article = addBubble(
      "assistant",
      response.message,
      "",
      response.message_html,
    );
    const bubble = article.querySelector(".chat-bubble");

    response.sections.forEach((section) => {
      const sectionElement = document.createElement("section");
      sectionElement.className = "chat-section";
      const heading = document.createElement("h2");
      heading.className = "h6";
      heading.textContent = section.title;
      sectionElement.appendChild(heading);

      section.items.forEach((item) => {
        const result = document.createElement("div");
        result.className = "chat-result";
        const title = document.createElement("strong");
        title.textContent = item.title;
        result.appendChild(title);
        if (item.subtitle) {
          const subtitle = document.createElement("div");
          subtitle.className = "chat-result-subtitle";
          subtitle.textContent = item.subtitle;
          result.appendChild(subtitle);
        }
        if (item.status) {
          const status = document.createElement("span");
          status.className = "chat-result-status";
          status.textContent = item.status;
          result.appendChild(status);
        }
        item.links.forEach((link) => {
          const wrapper = document.createElement("div");
          const anchor = document.createElement("a");
          anchor.href = link.url;
          anchor.textContent = link.label;
          if (link.url.startsWith("http")) {
            anchor.target = "_blank";
            anchor.rel = "noopener noreferrer";
          }
          wrapper.appendChild(anchor);
          result.appendChild(wrapper);
        });
        sectionElement.appendChild(result);
      });
      bubble.appendChild(sectionElement);
    });

    response.warnings.forEach((warning) => {
      const warningElement = document.createElement("div");
      warningElement.className = "chat-warning";
      warningElement.textContent = warning;
      bubble.appendChild(warningElement);
    });
    scrollToBottom();
  };

  const sendMessage = async (message) => {
    if (isSending) return;
    isSending = true;
    const previousHistory = [...history];
    addBubble("user", message);
    history.push({ role: "user", content: message });
    const status = addBubble(
      "status",
      form.dataset.checkingMessage,
      "chat-message-status",
    );
    submit.disabled = true;
    input.disabled = true;
    clear.disabled = true;

    try {
      const response = await fetch(form.dataset.endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ message, history: previousHistory }),
      });
      let data;
      try {
        data = await response.json();
      } catch (_error) {
        throw new Error(form.dataset.requestError);
      }
      if (!response.ok) throw new Error(data.error || form.dataset.requestError);
      status.remove();
      addResponse(data);
      history.push({
        role: "assistant",
        content: data.history_content || data.message,
      });
      trimHistory();
    } catch (error) {
      history = previousHistory;
      status.remove();
      addBubble("assistant", error.message);
    } finally {
      submit.disabled = false;
      input.disabled = false;
      clear.disabled = false;
      isSending = false;
      input.focus();
    }
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    input.value = "";
    sendMessage(message);
  });

  clear.addEventListener("click", () => {
    history = [];
    messages.replaceChildren();
    addBubble("assistant", form.dataset.clearedMessage);
  });
})();
