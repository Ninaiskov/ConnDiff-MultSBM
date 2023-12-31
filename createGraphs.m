
subjectIds = [	 101006 101309 101915 102008 102311 103414 104820 105115 105216 107321 107422 108525 108828 109123 110411 111312 111413 111716 113215 113922 114419 115320 117122 117324 118730 118932 119833 120111 120515 121618 122317 122620 123117 123420 123925 124220 124422 124826 126325 126628 127933 128127 128632 129028 130013 130316 130922 131924 132118 133019 		 133625 133928 135225 135932 136227 136833 137027 137128 137633 138231 138534 139637 140117 140420 ]
subjectIds = [	subjectIds 140824 140925 141422 141826 142828 144832 145834 146331 146432 147030 147737 148335 148941 149741 150423 150625 150726 151526 151728 152831 153025 153429 154431 154835 155635 		 156233 157336 158136 159441 160123 160830 161630 162228 162329 162733 163129 163432 163836 164030 164939 165032 165840 166438 167036 167743 168139 168341 169343 169444 171431  		 172130 172332 172534 173334 173435 173940 175035 175439 176542 177645 178748 ]
subjectIds = [	subjectIds 178849 178950 179346 180432 180836 180937 181131 181232 182739 182840 183034 185139 185442 187143 187547 187850 188347 189349 190031 191437 191841 192439 192540 192843 193239 		 194847 195041 195849 196144 197550 198350 198451 198855 199150 199251 199453 199958 200109 200614 201111 201414 201818 204016 204521 205725 205826 208024 208226 208327 209834 		 209935 210011 210415 210617 211215 211316 211417 211720 211922 212116 212318 214019 214221 214423 214726 217126 221319 224022 231928 233326 245333 246133 249947 250427 251833 ] 
subjectIds = [	subjectIds 280739 284646 285345 285446 289555 290136 293748 298051 298455 303624 308331 310621 316633 329440 334635 339847 352132 356948 361941 366446 371843 377451 382242 385450 386250 		 395958 397154 397760 397861 412528 414229 415837 422632 433839 441939 445543 448347 465852 479762 485757 486759 499566 500222 510326 519950 531536 540436 541943 545345 547046 		 559053 561242 562446 565452 567052 567961 568963 570243 573249 573451 580347 581349 583858 585862 586460 594156 599469 599671 601127 ] 



current_path='C:\mm\Data\HCPSingleSubjects';
modes={'dMRI','fMRIsession1','fMRIsession2'};
for q=1:length(modes)
    mode=modes{q};
    for networkNr = 1:5
        networkIds = subjectIds( (networkNr-1)*50 +1  : (networkNr)*50 );
        clear density;
        tt=0;
        for t=networkIds
            tt=tt+1;
            disp(['operating on subject ' num2str(tt)])
            switch mode
                case 'fMRIsession1'
                        load([current_path '\fMRI\' num2str(t) '_sess1.mat']);
                        if tt==1
                            A=network_sparse;
                        else
                            A=A+network_sparse;
                        end
                        density(tt)=nnz(network_sparse)/(prod((size(network_sparse)-[0 1]))/2);
                case 'fMRIsession2'
                        load([current_path '\fMRI\' num2str(t) '_sess2.mat']);
                        if tt==1
                            A=network_sparse;
                        else
                            A=A+network_sparse;
                        end
                        density(tt)=nnz(network_sparse)/(prod((size(network_sparse)-[0 1]))/2);
                 case 'dMRI'
                        load([current_path '\dMRI\' num2str(t) '.mat']);
                        if tt==1
                            A=dconn_thr;
                        else
                            A=A+dconn_thr;
                        end                    
                        density(tt)=nnz(dconn_thr)/(prod((size(dconn_thr)-[0 1]))/2);
            end        
        end
        save(['graph_' mode num2str(networkNr) '.mat'],'A','density','-v7.3');
    end
end
    