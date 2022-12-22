package test.domain.PO;

import lombok.Data;
import org.neo4j.ogm.annotation.GeneratedValue;
import org.neo4j.ogm.annotation.Id;

@Data
public class BaseNode {
    @Id
    @GeneratedValue
    private Long Id;
}
