//inhections.js

audio_type = {
    'mp3': 'audio/mpeg',
    'mp4': 'audio/mp4',
    'wav': 'audio/wav',
    'spx': 'audio/ogg',
    'ogg': 'audio/ogg'
}

function audio_content_type(ext){
    return audio_type[ext] || 'audio/mpeg'
    
}

function handleSoundLink(event, element) {
    var tag = element.getAttribute("href");
    if (!tag) {
        return false;
    }
    var url = tag.trim();
    if (!url) {
        return false;
    }
    var lower = url.toLowerCase();
    if (!lower.startsWith("/sound/")) {
        return false;
    }
    var relativePath = url;
    if (!relativePath) {
        return false;
    }
    event.preventDefault();
    if (event.stopImmediatePropagation) {
        event.stopImmediatePropagation();
    } else {
        event.stopPropagation();
    }
    var audioElement = document.getElementById("audiotag");
    if (!audioElement) {
        return false;
    }
    audioElement.setAttribute("src", relativePath);
    audioElement.setAttribute("type", audio_content_type(relativePath.slice(-3)));
    try {
        audioElement.play();
    } catch (err) {
    }
    return true;
}

document.addEventListener("click", function(event){
    var node = event.target;
    while (node && node !== document) {
        if (node.tagName && node.tagName.toLowerCase() === "a") {
            if (handleSoundLink(event, node)) {
                return false;
            }
            break;
        }
        node = node.parentNode;
    }
}, true);
