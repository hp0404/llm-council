import { useState, useEffect } from 'react';
import './ModelSelector.css';

export default function ModelSelector({
  isOpen,
  onClose,
  conversationId,
  availableModels,
  currentConfig,
  onSave,
}) {
  const [councilModels, setCouncilModels] = useState([]);
  const [chairmanModel, setChairmanModel] = useState('');
  const [councilSearch, setCouncilSearch] = useState('');
  const [chairmanSearch, setChairmanSearch] = useState('');

  useEffect(() => {
    if (currentConfig) {
      setCouncilModels(currentConfig.council_models || []);
      setChairmanModel(currentConfig.chairman_model || '');
    }
  }, [currentConfig]);

  if (!isOpen) return null;

  const handleSave = () => {
    onSave(councilModels, chairmanModel);
    onClose();
  };

  const toggleCouncilModel = (modelId) => {
    if (councilModels.includes(modelId)) {
      setCouncilModels(councilModels.filter((id) => id !== modelId));
    } else {
      setCouncilModels([...councilModels, modelId]);
    }
  };

  const removeCouncilModel = (modelId) => {
    setCouncilModels(councilModels.filter((id) => id !== modelId));
  };

  const filterModels = (search) => {
    if (!search.trim()) return availableModels;
    const lowerSearch = search.toLowerCase();
    return availableModels.filter(
      (model) =>
        model.id.toLowerCase().includes(lowerSearch) ||
        model.name.toLowerCase().includes(lowerSearch)
    );
  };

  const councilFilteredModels = filterModels(councilSearch);
  const chairmanFilteredModels = filterModels(chairmanSearch);

  return (
    <div className="model-selector-overlay" onClick={onClose}>
      <div
        className="model-selector-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="model-selector-header">
          <h2>Configure Models</h2>
          <button className="close-button" onClick={onClose}>
            ×
          </button>
        </div>

        {/* Council Models Section */}
        <div className="model-section">
          <h3>
            Council Members
            <span className="model-count">
              ({councilModels.length} selected)
            </span>
          </h3>
          
          <input
            type="text"
            className="search-box"
            placeholder="Search models..."
            value={councilSearch}
            onChange={(e) => setCouncilSearch(e.target.value)}
          />

          <div className="selected-models">
            {councilModels.length === 0 ? (
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                No council members selected
              </span>
            ) : (
              councilModels.map((modelId) => (
                <div key={modelId} className="selected-model-tag">
                  {modelId}
                  <button
                    className="remove-model"
                    onClick={() => removeCouncilModel(modelId)}
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>

          <div className="model-list">
            {councilFilteredModels.length === 0 ? (
              <div className="empty-list">No models found</div>
            ) : (
              councilFilteredModels.map((model) => (
                <div
                  key={model.id}
                  className={`model-item ${
                    councilModels.includes(model.id) ? 'selected' : ''
                  }`}
                  onClick={() => toggleCouncilModel(model.id)}
                >
                  <input
                    type="checkbox"
                    checked={councilModels.includes(model.id)}
                    onChange={() => {}}
                  />
                  <div className="model-info">
                    <div className="model-name">{model.name}</div>
                    <div className="model-id">{model.id}</div>
                    {model.description && (
                      <div className="model-description">
                        {model.description.slice(0, 150)}
                        {model.description.length > 150 ? '...' : ''}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Chairman Model Section */}
        <div className="model-section">
          <h3>
            Chairman Model
            <span className="model-count">
              {chairmanModel ? '(1 selected)' : '(none selected)'}
            </span>
          </h3>
          
          <input
            type="text"
            className="search-box"
            placeholder="Search models..."
            value={chairmanSearch}
            onChange={(e) => setChairmanSearch(e.target.value)}
          />

          {chairmanModel && (
            <div className="selected-models">
              <div className="selected-model-tag">
                {chairmanModel}
                <button
                  className="remove-model"
                  onClick={() => setChairmanModel('')}
                >
                  ×
                </button>
              </div>
            </div>
          )}

          <div className="model-list">
            {chairmanFilteredModels.length === 0 ? (
              <div className="empty-list">No models found</div>
            ) : (
              chairmanFilteredModels.map((model) => (
                <div
                  key={model.id}
                  className={`model-item ${
                    chairmanModel === model.id ? 'selected' : ''
                  }`}
                  onClick={() => setChairmanModel(model.id)}
                >
                  <input
                    type="radio"
                    checked={chairmanModel === model.id}
                    onChange={() => {}}
                  />
                  <div className="model-info">
                    <div className="model-name">{model.name}</div>
                    <div className="model-id">{model.id}</div>
                    {model.description && (
                      <div className="model-description">
                        {model.description.slice(0, 150)}
                        {model.description.length > 150 ? '...' : ''}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="model-selector-actions">
          <button className="cancel-button" onClick={onClose}>
            Cancel
          </button>
          <button
            className="save-button"
            onClick={handleSave}
            disabled={councilModels.length === 0 || !chairmanModel}
          >
            Save Configuration
          </button>
        </div>
      </div>
    </div>
  );
}

