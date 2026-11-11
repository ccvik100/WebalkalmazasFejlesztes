// A fájl tartalmát Blazor állítja össze, a mentést a böngésző indítja.
window.saveTranscript = async (filename, type, stream) => {
    const bytes = await stream.arrayBuffer();
    const url = URL.createObjectURL(new Blob([bytes], { type: `${type};charset=utf-8` }));
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
};
