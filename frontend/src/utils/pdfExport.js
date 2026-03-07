import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

/**
 * Captures a React DOM element and exports it as a downloaded PDF file.
 * 
 * @param {HTMLElement} elementRef - The reference to the DOM element to capture.
 * @param {string} filename - The desired name of the downloaded file.
 */
export const exportElementToPDF = async (elementRef, filename = 'agrovisus-report.pdf') => {
    if (!elementRef) {
        console.error("No element provided for PDF export.");
        return false;
    }

    try {
        // 1. Capture the DOM element as a high-fidelity canvas
        const canvas = await html2canvas(elementRef, {
            scale: 2, // 2x scale for Retina/high-res crispness
            useCORS: true, // Allow external images/fonts if any
            backgroundColor: '#0a0f0d' // Match the dark theme background explicitly
        });

        // 2. Convert canvas to base64 image
        const imgData = canvas.toDataURL('image/jpeg', 0.95);

        // 3. Determine PDF orientation dynamically based on screen width
        // If the screen is wider than it is tall (like a desktop), use landscape paper.
        // If it's a mobile phone (taller than wide), use portrait paper.
        const originalWidth = canvas.width;
        const originalHeight = canvas.height;
        const orientation = originalWidth > originalHeight ? 'landscape' : 'portrait';

        const pdf = new jsPDF({
            orientation: orientation,
            unit: 'mm',
            format: 'a4'
        });

        // 4. Calculate smart scaling to fit within page with margins
        const MARGIN_MM = 15; // 15mm border around the whole page
        const pdfWidth = pdf.internal.pageSize.getWidth() - (MARGIN_MM * 2);
        const pdfHeight = pdf.internal.pageSize.getHeight() - (MARGIN_MM * 2);

        // Figure out if we need to scale by width or height
        const ratioCanvas = originalWidth / originalHeight;
        const ratioPdf = pdfWidth / pdfHeight;

        let printWidth, printHeight;

        if (ratioCanvas > ratioPdf) {
            // Screen is wider than PDF (it will hit left/right boundaries first)
            printWidth = pdfWidth;
            printHeight = pdfWidth / ratioCanvas;
        } else {
            // Screen is taller than PDF (it will hit top/bottom boundaries first)
            printHeight = pdfHeight;
            printWidth = pdfHeight * ratioCanvas;
        }

        // 5. Center align horizontally
        const xOffset = MARGIN_MM + ((pdfWidth - printWidth) / 2);
        const yOffset = MARGIN_MM; // Snap to top with margin

        // 6. Handle multi-page pagination (if it somehow still bleeds over)
        let heightLeft = printHeight;
        let position = yOffset;

        pdf.addImage(imgData, 'JPEG', xOffset, position, printWidth, printHeight);
        heightLeft -= pdfHeight;

        while (heightLeft > 0) {
            position = heightLeft - printHeight + MARGIN_MM;
            pdf.addPage();
            pdf.addImage(imgData, 'JPEG', xOffset, position, printWidth, printHeight);
            heightLeft -= pdfHeight;
        }

        // 7. Trigger download
        pdf.save(filename);
        return true;

    } catch (error) {
        console.error("Error generating PDF:", error);
        return false;
    }
};
