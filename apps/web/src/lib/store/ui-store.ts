import { create } from "zustand";

type UiState = {
  isProjectPanelOpen: boolean;
  setProjectPanelOpen: (value: boolean) => void;
};

export const useUiStore = create<UiState>((set) => ({
  isProjectPanelOpen: false,
  setProjectPanelOpen: (value) => set({ isProjectPanelOpen: value }),
}));
